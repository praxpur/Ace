"""Mirror the headless login page into the app so the user can solve the captcha in place.

All Playwright calls happen on the worker thread (inside ``pump``); the GUI thread only
pushes plain input dicts and reads the latest JPEG frame.
"""
import base64
import threading
import time
from collections import deque

from .models import Event

MAX_PENDING = 300
INPUT_TYPES = {"down", "move", "up", "click", "wheel", "text", "key"}


class LoginRelay:
    def __init__(self):
        self.lock = threading.Lock()
        self.inputs = deque(maxlen=MAX_PENDING)
        self.emit = lambda event: None
        self.reset()

    def reset(self):
        with self.lock:
            self.inputs.clear()
            self.latest = None
            self.seq = 0
            self.size = (1280, 720)
            self.active = False
            self.last_shot = 0.0

    def bind(self, emit):
        self.emit = emit
        self.reset()

    # ---- GUI thread -------------------------------------------------
    def push(self, item) -> bool:
        if not isinstance(item, dict) or item.get("type") not in INPUT_TYPES:
            return False
        with self.lock:
            if not self.active:
                return False
            self.inputs.append(item)
        return True

    def frame(self, since=0) -> dict:
        with self.lock:
            fresh = self.latest is not None and self.seq != since
            return {"active": self.active, "seq": self.seq, "width": self.size[0],
                    "height": self.size[1], "image": self.latest if fresh else None}

    # ---- worker thread ----------------------------------------------
    def _apply(self, page, item):
        width, height = self.size
        kind = item["type"]
        try:
            if kind in {"down", "move", "up", "click", "wheel"}:
                x = min(max(float(item.get("x", 0)), 0), width - 1)
                y = min(max(float(item.get("y", 0)), 0), height - 1)
                page.mouse.move(x, y)
                if kind == "down":
                    page.mouse.down()
                elif kind == "up":
                    page.mouse.up()
                elif kind == "click":
                    page.mouse.down()
                    page.mouse.up()
                elif kind == "wheel":
                    page.mouse.wheel(0, float(item.get("dy", 0)))
            elif kind == "text":
                page.keyboard.type(str(item.get("text", ""))[:200])
            elif kind == "key":
                page.keyboard.press(str(item.get("key", ""))[:30])
        except Exception:
            pass  # invalid key name or page mid-navigation

    def _shoot(self, page):
        try:
            data = page.screenshot(type="jpeg", quality=60, timeout=2000)
        except Exception:
            return
        viewport = page.viewport_size or {"width": 1280, "height": 720}
        with self.lock:
            self.latest = base64.b64encode(data).decode("ascii")
            self.seq += 1
            self.size = (viewport["width"], viewport["height"])
            self.last_shot = time.monotonic()

    def pump(self, page, duration=0.25):
        with self.lock:
            opened = not self.active
            self.active = True
        if opened:
            self.emit(Event("login_open", {}))
        deadline = time.monotonic() + duration
        while True:
            applied = False
            while True:
                with self.lock:
                    item = self.inputs.popleft() if self.inputs else None
                if item is None:
                    break
                self._apply(page, item)
                applied = True
            if applied or time.monotonic() - self.last_shot >= 0.3:
                self._shoot(page)
            if time.monotonic() >= deadline:
                return
            page.wait_for_timeout(40)

    def close(self):
        with self.lock:
            was_active = self.active
            self.active = False
            self.latest = None
            self.inputs.clear()
        if was_active:
            self.emit(Event("login_done", {}))


RELAY = LoginRelay()
