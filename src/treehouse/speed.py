"""Choose speeds from the course player's own enabled Video.js menu only."""
import re
from dataclasses import dataclass

from .errors import UserCancelled


def parse_rate(text):
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:[x×]|倍)(?:\s|[,，]|$)", text, re.I)
    if not match:
        return None
    rate = float(match.group(1))
    return rate if .25 <= rate <= 16 else None


def allowed_rate(requested, available):
    candidates = [rate for rate in available if 1 <= rate <= requested]
    return max(candidates) if candidates else None


@dataclass(frozen=True)
class SpeedResult:
    requested: float
    actual: float
    supported: bool
    message: str


def apply_course_speed(page, video, requested, token):
    def current():
        return float(video.evaluate("v => v.playbackRate"))

    def unchanged(reason):
        actual = current()
        return SpeedResult(requested, actual, False, f"{reason}，按课程当前 {actual:g}× 播放。")

    token.check()
    actual = current()
    if abs(actual - requested) < .001:
        return SpeedResult(requested, actual, True, f"当前播放速度为 {actual:g}×。")
    try:
        root = video.locator(
            "xpath=ancestor::*[contains(concat(' ',normalize-space(@class),' '),' video-js ')][1]")
        if root.count() != 1:
            return unchanged("课程未提供受支持的倍速菜单")
        root.hover(timeout=1500)
        controls = root.locator(".vjs-playback-rate:has(.vjs-menu-item)")
        if controls.count() != 1 or not controls.is_visible():
            return unchanged("课程未开放倍速控件")
        control = controls.first
        if (control.get_attribute("aria-disabled") == "true"
                or "vjs-disabled" in (control.get_attribute("class") or "").split()):
            return unchanged("课程已禁用倍速控件")
        control.hover(timeout=1500)
        items = control.locator(".vjs-menu-item")
        rows = items.evaluate_all("""items => items.map(item => ({
            text: item.textContent.trim(), disabled: item.getAttribute('aria-disabled') === 'true'
                || item.hasAttribute('disabled') || item.classList.contains('vjs-disabled')
        }))""")
        choices = [(parse_rate(row["text"]), index) for index, row in enumerate(rows)
                   if not row["disabled"]]
        choices = [(rate, index) for rate, index in choices if rate is not None]
        target = allowed_rate(requested, [rate for rate, _ in choices])
        if target is None:
            return unchanged("课程菜单没有符合请求的可用速度")
        item = items.nth(next(index for rate, index in choices if rate == target))
        if not item.is_visible():
            buttons = control.locator("button")
            trigger = buttons.first if buttons.count() else control
            trigger.click(timeout=1500)
        token.check()
        item.click(timeout=1500)
        for _ in range(6):
            token.check()
            actual = current()
            if abs(actual - target) < .001:
                break
            page.wait_for_timeout(50)
        if abs(actual - target) >= .001:
            return unchanged("课程未接受倍速切换")
        detail = f"（请求 {requested:g}×，菜单可用的最高对应档位）" if target != requested else ""
        return SpeedResult(requested, actual, True, f"已通过课程倍速菜单选择 {target:g}×{detail}。")
    except UserCancelled:
        raise
    except Exception:
        # A missing / changing menu must not fail an otherwise playable video.
        token.check()
        return unchanged("课程倍速菜单暂不可用")
