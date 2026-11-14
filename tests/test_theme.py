"""Theme persistence and opt-in browser checks against the built frontend."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


class ThemeConfigTest(unittest.TestCase):
    def test_theme_survives_new_api_instance_without_changing_other_settings(self):
        import gui_main

        with tempfile.TemporaryDirectory() as directory, patch.object(
                gui_main, "GUI_CONFIG_PATH", str(Path(directory) / "gui_config.json")):
            api = gui_main.Api()
            self.assertEqual(api.get_config()["data"]["appearance"]["theme"], "system")
            api._config["common"]["speed"] = 1.5
            for theme in ("dark", "light", "system"):
                result = api.save_config_only(json.dumps({"appearance": {"theme": theme}}))
                self.assertTrue(result["success"])
                restored = gui_main.Api().get_config()["data"]
                self.assertEqual(restored["appearance"]["theme"], theme)
                self.assertEqual(restored["common"]["speed"], 1.5)


@unittest.skipUnless(os.getenv("TREE_RUN_FRONTEND_TESTS") == "1", "opt-in frontend browser test")
class ThemeBrowserTest(unittest.TestCase):
    def test_saved_mode_and_live_system_changes(self):
        from playwright.sync_api import sync_playwright

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        root = Path(__file__).resolve().parents[1]
        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(
            QuietHandler, directory=str(root / "gui_dist")))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        saved = {"theme": "system"}

        def api(method, args):
            if method == "get_config":
                return {"success": True, "data": {"appearance": saved.copy()}}
            if method == "save_config_only":
                saved.update(json.loads(args[0])["appearance"])
            return {"success": True, "data": {}, "events": []}

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--disable-gpu"], executable_path=(
                    os.getenv("TREEHOUSE_BROWSER_EXECUTABLE") or None))
                # Each launch uses fresh browser storage, like PyWebView's private session.
                for initial_scheme in ("light", "dark"):
                    context = browser.new_context(color_scheme=initial_scheme)
                    page = context.new_page()
                    page.set_default_timeout(5000)
                    page.expose_function("desktopApi", api)
                    page.add_init_script("""window.pywebview = {api: new Proxy({}, {
                      get: (_, method) => (...args) => window.desktopApi(method, args)
                    })};
                    addEventListener('DOMContentLoaded', () => setTimeout(() =>
                      dispatchEvent(new Event('pywebviewready')), 100));""")
                    page.goto(f"http://127.0.0.1:{server.server_port}")
                    page.wait_for_function("window.localStorage.getItem('theme') === 'system'")
                    page.wait_for_function("document.documentElement.classList.contains('dark') === "
                                           + str(initial_scheme == "dark").lower())
                    page.emulate_media(color_scheme="dark")
                    page.wait_for_function("document.documentElement.classList.contains('dark')")
                    page.emulate_media(color_scheme="light")
                    page.wait_for_function("!document.documentElement.classList.contains('dark')")
                    # Explicit dark must ignore subsequent system changes.
                    page.locator(".theme-toggle .el-select").click()
                    page.get_by_role("option", name="深色模式", exact=True).click()
                    page.wait_for_function("document.documentElement.classList.contains('dark')")
                    page.wait_for_timeout(100)
                    self.assertEqual(saved["theme"], "dark")
                    # A fresh session must restore the desktop config even with no browser cache.
                    context.close()
                    context = browser.new_context(color_scheme="light")
                    page = context.new_page()
                    page.set_default_timeout(5000)
                    page.expose_function("desktopApi", api)
                    page.add_init_script("""window.pywebview = {api: new Proxy({}, {
                      get: (_, method) => (...args) => window.desktopApi(method, args)
                    })};
                    addEventListener('DOMContentLoaded', () => setTimeout(() =>
                      dispatchEvent(new Event('pywebviewready')), 100));""")
                    page.goto(f"http://127.0.0.1:{server.server_port}")
                    page.wait_for_function("document.documentElement.classList.contains('dark')")
                    page.locator(".theme-toggle .el-select").click()
                    page.get_by_role("option", name="浅色模式", exact=True).click()
                    page.emulate_media(color_scheme="dark")
                    page.wait_for_function("!document.documentElement.classList.contains('dark')")
                    page.locator(".theme-toggle .el-select").click()
                    page.get_by_role("option", name="跟随系统", exact=True).click()
                    page.wait_for_function("document.documentElement.classList.contains('dark')")
                    page.wait_for_timeout(100)
                    self.assertEqual(saved["theme"], "system")
                    context.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
