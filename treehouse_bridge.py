"""Expose the Treehouse workflow to the shared PyWebView frontend."""
import sys
import queue
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from treehouse.config import COURSE_CENTER_URL, DEFAULT_STATE_PATH, Settings
from treehouse.controller import JobController


class TreehouseBridge:
    def __init__(self):
        self._treehouse = JobController()

    def treehouse_defaults(self):
        return {"success": True, "data": {
            "url": COURSE_CENTER_URL,
            "state_path": str(DEFAULT_STATE_PATH),
            "has_state": DEFAULT_STATE_PATH.is_file(),
        }}

    def treehouse_start(self, options):
        if self._treehouse.running:
            return {"success": False, "msg": "智慧树任务仍在运行。"}
        try:
            state = Path(options.get("state_path") or DEFAULT_STATE_PATH).expanduser()
            remember = bool(options.get("remember", True))
            settings = Settings(
                start_url=options.get("url") or COURSE_CENTER_URL,
                headless=bool(options.get("headless", False)),
                playback_rate=float(options.get("speed", 1)),
                connection_mode=options.get("connection_mode", "system"),
                state_path=state if state.is_file() else None,
                save_state_path=state if remember else None,
            )
            run_id = self._treehouse.start(settings)
            return {"success": True, "run_id": run_id}
        except Exception as exc:
            return {"success": False, "msg": str(exc)}

    def treehouse_updates(self):
        events = []
        while len(events) < 200:
            try:
                run_id, event = self._treehouse.events.get_nowait()
            except queue.Empty:
                break
            if run_id == self._treehouse.run_id:
                events.append({"kind": event.kind, "data": event.data})
        return {"success": True, "running": self._treehouse.running, "events": events}

    def treehouse_select(self, request_id, keys):
        if not isinstance(keys, list) or not keys:
            return {"success": False, "msg": "请至少选择一项。"}
        accepted = self._treehouse.resolve(request_id, keys)
        return {"success": accepted, "msg": "选择已失效，请重新连接。" if not accepted else ""}

    def treehouse_stop(self):
        self._treehouse.stop()
        return {"success": True}
