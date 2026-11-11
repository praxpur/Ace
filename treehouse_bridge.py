"""Expose the Treehouse workflow to the shared PyWebView frontend."""
import sys
import queue
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from treehouse.config import COURSE_CENTER_URL, DEFAULT_STATE_PATH, PLAYBACK_RATES, Settings
from treehouse.controller import JobController
from treehouse.login_relay import RELAY


def normalize_treehouse_options(options: dict | None = None, defaults: dict | None = None) -> dict:
    base = {
        "url": COURSE_CENTER_URL,
        "state_path": str(DEFAULT_STATE_PATH),
        "remember": True,
        "headless": False,
        "connection_mode": "system",
        "speed": 1.0,
        "embedded_login": True,
        "username": "",
        "password": "",
    }
    if defaults:
        base.update({k: v for k, v in defaults.items() if v is not None and k in base})
    if options:
        base.update({k: v for k, v in options.items() if v is not None and k in base})

    url = str(base.get("url") or COURSE_CENTER_URL).strip() or COURSE_CENTER_URL
    state_raw = str(base.get("state_path") or DEFAULT_STATE_PATH).strip() or str(DEFAULT_STATE_PATH)
    remember = bool(base.get("remember", True))
    headless = bool(base.get("headless", False))
    connection_mode = str(base.get("connection_mode") or "system").strip()
    if connection_mode not in ("system", "direct"):
        connection_mode = "system"

    try:
        raw_speed = float(base.get("speed", 1.0))
    except (TypeError, ValueError):
        raw_speed = 1.0
    speed = min(PLAYBACK_RATES, key=lambda r: abs(r - raw_speed))

    return {
        "url": url,
        "state_path": state_raw,
        "remember": remember,
        "headless": headless,
        "connection_mode": connection_mode,
        "speed": speed,
        "embedded_login": bool(base.get("embedded_login", True)),
        "username": str(base.get("username") or "").strip(),
        "password": str(base.get("password") or ""),
    }


class TreehouseBridge:
    def __init__(self):
        self._treehouse = JobController()

    def _stored_treehouse_config(self) -> dict:
        config = getattr(self, "_config", None)
        if isinstance(config, dict):
            return config.get("treehouse", {}) or {}
        return {}

    def _persist_treehouse_config(self, normalized: dict):
        config = getattr(self, "_config", None)
        if isinstance(config, dict):
            config.setdefault("treehouse", {}).update(normalized)
            saver = getattr(self, "_save_config", None)
            if callable(saver):
                saver()

    def treehouse_defaults(self):
        normalized = normalize_treehouse_options(self._stored_treehouse_config())
        state = Path(normalized["state_path"]).expanduser()
        return {
            "success": True,
            "data": {
                **normalized,
                "has_state": state.is_file(),
            },
        }

    def treehouse_save_config(self, options):
        try:
            normalized = normalize_treehouse_options(options, self._stored_treehouse_config())
            self._persist_treehouse_config(normalized)
            state = Path(normalized["state_path"]).expanduser()
            return {
                "success": True,
                "msg": "智慧树配置已保存",
                "data": {
                    **normalized,
                    "has_state": state.is_file(),
                },
            }
        except Exception as exc:
            return {"success": False, "msg": str(exc)}

    def treehouse_start(self, options):
        if self._treehouse.running:
            return {"success": False, "msg": "智慧树任务仍在运行，请先停止当前任务。"}
        try:
            normalized = normalize_treehouse_options(options, self._stored_treehouse_config())
            self._persist_treehouse_config(normalized)
            state = Path(normalized["state_path"]).expanduser()
            has_state = state.is_file()
            if normalized["headless"] and not has_state and not normalized["embedded_login"]:
                return {
                    "success": False,
                    "msg": "尚未生成登录态文件。首次登录请先关闭“无头模式运行”，在弹出的浏览器中完成登录。",
                }
            settings = Settings(
                start_url=normalized["url"],
                headless=normalized["headless"] or normalized["embedded_login"],
                embedded_login=normalized["embedded_login"],
                playback_rate=float(normalized["speed"]),
                connection_mode=normalized["connection_mode"],
                username=normalized["username"],
                password=normalized["password"],
                state_path=state if has_state else None,
                save_state_path=state if normalized["remember"] else None,
            )
            run_id = self._treehouse.start(settings)
            return {"success": True, "run_id": run_id, "data": {**normalized, "has_state": has_state}}
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

    def treehouse_cancel_selection(self, request_id):
        if request_id:
            self._treehouse.resolve(request_id, None)
        self._treehouse.stop()
        return {"success": True}

    def treehouse_login_frame(self, since=0):
        return {"success": True, **RELAY.frame(int(since or 0))}

    def treehouse_login_input(self, item):
        return {"success": RELAY.push(item)}

    def treehouse_stop(self):
        self._treehouse.stop()
        return {"success": True}
