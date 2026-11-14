"""Opt-in browser regression for the built desktop frontend (no real account)."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading
import unittest


@unittest.skipUnless(os.getenv("TREE_RUN_FRONTEND_TESTS") == "1", "opt-in frontend browser test")
class FrontendLoginTest(unittest.TestCase):
    def test_login_visible_after_connection_switches_to_run_panel(self):
        from playwright.sync_api import sync_playwright

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        root = Path(__file__).resolve().parents[1]
        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
            QuietHandler, directory=str(root / "gui_dist")))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--disable-gpu"], executable_path=(
                    os.getenv("TREEHOUSE_BROWSER_EXECUTABLE") or None))
                page = browser.new_page(viewport={"width": 1120, "height": 780})
                page.add_init_script("""(() => {
                  let running = false, opened = false, finished = false;
                  window.loginInputs = [];
                  window.pywebview = {api: new Proxy({}, {get: (_, method) => async (...args) => {
                    if (method === 'treehouse_start') { running = true; return {success: true}; }
                    if (method === 'treehouse_stop') { running = false; finished = true; }
                    if (method === 'treehouse_updates') {
                      const events = [];
                      if (running && !opened) { opened = true; events.push({kind: 'login_open'}); }
                      if (finished) { finished = false; events.push({kind: 'finished', data: {status: 'cancelled'}}); }
                      return {success: true, running, events};
                    }
                    if (method === 'treehouse_login_frame') return {success: true, seq: 1,
                      width: 1280, height: 720,
                      image: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='};
                    if (method === 'treehouse_login_input') window.loginInputs.push(args[0]);
                    return {success: true, data: {}};
                  }})};
                  addEventListener('DOMContentLoaded', () => setTimeout(() =>
                    dispatchEvent(new Event('pywebviewready')), 100));
                })();""")
                page.goto(f"http://127.0.0.1:{server.server_port}")
                page.get_by_role("button", name="智慧树", exact=True).click()
                page.get_by_role("button", name="保存配置并连接课程", exact=True).click()
                dialog = page.get_by_role("dialog", name="智慧树登录", exact=False)
                dialog.wait_for(state="visible", timeout=5000)
                image = dialog.locator(".th-login-frame")
                image.wait_for(state="visible")
                image.click(position={"x": 20, "y": 20})
                page.keyboard.type("abc")
                page.wait_for_function("window.loginInputs.some(i => i.type === 'text' && i.text === 'c')")
                self.assertTrue(page.evaluate("window.loginInputs.some(i => i.type === 'down')"))
                self.assertTrue(page.evaluate("window.loginInputs.some(i => i.type === 'up')"))
                dialog.get_by_role("button", name="取消连接").click()
                dialog.wait_for(state="hidden", timeout=5000)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
