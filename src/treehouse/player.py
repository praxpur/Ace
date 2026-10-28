import math
import time
from dataclasses import dataclass

from .errors import PlaybackError
from .speed import apply_course_speed


def finite_number(value, default=0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and number >= 0 else default


@dataclass(frozen=True)
class MediaSnapshot:
    current: float
    duration: float
    paused: bool
    ended: bool
    started: bool
    connected: bool
    loop: bool
    error: str | None
    playback_rate: float = 1.0

    @classmethod
    def from_dict(cls, data):
        return cls(
            finite_number(data.get("current")), finite_number(data.get("duration")),
            bool(data.get("paused")), bool(data.get("ended")), bool(data.get("started")),
            bool(data.get("connected")), bool(data.get("loop")), data.get("error"),
            finite_number(data.get("playback_rate"), 1.0) or 1.0,
        )

    def progress(self) -> dict:
        return {
            "current": self.current, "duration": self.duration,
            "percent": min(100.0, 100 * self.current / self.duration) if self.duration else 0.0,
            "paused": self.paused, "ended": self.ended,
            "playback_rate": self.playback_rate,
        }


class PlaybackTracker:
    def __init__(self, started_at, total_timeout, stall_timeout):
        self.started_at = started_at
        self.total_timeout = total_timeout
        self.stall_timeout = stall_timeout
        self.last_advance = started_at
        self.last_current = None
        self.played = False

    def observe(self, snapshot: MediaSnapshot, now: float) -> bool:
        if not snapshot.connected:
            raise PlaybackError("播放中的视频元素被移除或替换。")
        if snapshot.error:
            raise PlaybackError(f"播放器错误：{snapshot.error}")
        if snapshot.loop:
            raise PlaybackError("播放器开启了循环，无法验证视频自然结束。")
        if self.last_current is None:
            self.last_current = snapshot.current
        elif snapshot.current > self.last_current + 0.01:
            self.played = True
            self.last_current = snapshot.current
            self.last_advance = now
        if snapshot.ended and snapshot.started:
            return True
        if now - self.started_at >= self.total_timeout:
            raise PlaybackError("视频未在限定时间内自然结束。")
        if now - self.last_advance >= self.stall_timeout:
            detail = "视频处于暂停状态。" if snapshot.paused else "播放进度长时间没有前进。"
            raise PlaybackError(detail + "请检查播放器状态和网络。")
        return False


class VideoPlayer:
    def __init__(self, settings, token, progress_callback, log_callback=lambda message: None,
                 popup_handler=None):
        self.settings = settings
        self.token = token
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.popup_handler = popup_handler

    def play(self, page, locator) -> None:
        state = locator.evaluate_handle("""v => {
            if (!(v instanceof HTMLVideoElement)) throw new Error('目标不是 HTML5 video');
            const state = {video: v, started: false, ended: false, error: null};
            v.addEventListener('playing', () => { state.started = true; });
            v.addEventListener('ended', () => { state.ended = true; }, {once: true});
            return state;
        }""")
        try:
            source_deadline = time.monotonic() + self.settings.page_timeout
            while not state.evaluate("""state => {
                const v = state.video;
                return Boolean(v.currentSrc || v.getAttribute('src') || v.querySelector('source'));
            }"""):
                self.token.check()
                if time.monotonic() >= source_deadline:
                    raise PlaybackError("播放器未在限定时间内提供视频媒体源。")
                page.wait_for_timeout(self.settings.poll_interval * 1000)
            state.evaluate("""state => {
                if (state.video.readyState === 0) state.video.load();
            }""")
            while True:
                self.token.check()
                metadata = state.evaluate("""state => ({
                    ready: state.video.readyState >= 1,
                    error: state.video.error ? state.video.error.message : null
                })""")
                if metadata["error"]:
                    raise PlaybackError("媒体加载失败：" + metadata["error"])
                if metadata["ready"]:
                    break
                if time.monotonic() >= source_deadline:
                    raise PlaybackError("播放器未在限定时间内加载视频元数据。")
                page.wait_for_timeout(self.settings.poll_interval * 1000)
            state.evaluate("""(state, muted) => {
                state.video.muted = muted;
                state.video.play().catch(error => {
                    state.error = error.name + ': ' + error.message;
                });
            }""", self.settings.muted)
            speed = apply_course_speed(page, locator, self.settings.playback_rate, self.token)
            self.log_callback(speed.message)
            last_rate = speed.actual
            tracker = PlaybackTracker(
                time.monotonic(), self.settings.video_timeout, self.settings.stall_timeout
            )
            last_emit = 0.0
            while True:
                self.token.check()
                raw = state.evaluate("""state => {
                    const v = state.video;
                    return {
                        current: v.currentTime,
                        duration: Number.isFinite(v.duration) ? v.duration : null,
                        paused: v.paused,
                        ended: state.ended || v.ended,
                        started: state.started,
                        connected: v.isConnected,
                        loop: v.loop,
                        playback_rate: v.playbackRate,
                        error: state.error || (v.error ? String(v.error.code) + ': ' + v.error.message : null)
                    };
                }""")
                snapshot = MediaSnapshot.from_dict(raw)
                if (snapshot.paused and not snapshot.ended and self.popup_handler is not None
                        and self.popup_handler(page, self.token)):
                    self.log_callback("检测到课中弹题，已自动选择选项并关闭，继续播放。")
                    state.evaluate("""(state, muted) => {
                        if (state.video.paused && !state.video.ended) {
                            state.video.muted = muted;
                            state.video.play().catch(error => {
                                state.error = error.name + ': ' + error.message;
                            });
                        }
                    }""", self.settings.muted)
                    tracker.last_advance = time.monotonic()
                    page.wait_for_timeout(self.settings.poll_interval * 1000)
                    continue
                if abs(snapshot.playback_rate - last_rate) > .001:
                    self.log_callback(f"课程实际播放速度已变为 {snapshot.playback_rate:g}×，将按该速度继续。")
                    last_rate = snapshot.playback_rate
                now = time.monotonic()
                done = tracker.observe(snapshot, now)
                if done or now - last_emit >= 0.5:
                    self.progress_callback(snapshot.progress())
                    last_emit = now
                if done:
                    return
                page.wait_for_timeout(self.settings.poll_interval * 1000)
        finally:
            state.dispose()
