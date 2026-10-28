"""Locate the browser shipped alongside a frozen Windows application."""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    browsers = Path(sys._MEIPASS) / "browsers"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    matches = sorted(browsers.glob("chromium-*/chrome-win64/chrome.exe"))
    if matches:
        os.environ.setdefault("TREEHOUSE_BROWSER_EXECUTABLE", str(matches[-1]))
