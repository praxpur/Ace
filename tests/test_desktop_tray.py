import threading
import unittest
from unittest.mock import Mock, patch

from desktop_tray import DesktopTray


class DesktopTrayTest(unittest.TestCase):
    def setUp(self):
        self.window = Mock()
        self.api = Mock()
        self.api._running_thread = None
        self.api._treehouse.worker = None
        self.backend = Mock()
        self.backend.dispatch.side_effect = lambda callback: callback()
        self.tray = DesktopTray(self.window, self.api, "app.ico", shutdown_timeout=0.02)
        self.tray.backend = self.backend

    def test_close_hides_and_keeps_workers_running(self):
        self.assertTrue(self.tray.close_requested())
        self.assertTrue(self.tray.hidden)
        self.backend.hide_window.assert_called_once()
        self.api.stop_tasks.assert_not_called()
        self.api.treehouse_stop.assert_not_called()
        self.window.destroy.assert_not_called()

    def test_restore_and_repeat_hide_only_notify_once(self):
        self.tray.hide()
        self.tray.show()
        self.assertFalse(self.tray.hidden)
        self.backend.show_window.assert_called_once()
        self.tray.hide()
        self.backend.notify.assert_called_once()

    def test_notification_failure_does_not_close_window(self):
        self.backend.notify.side_effect = RuntimeError("notifications unavailable")
        self.assertTrue(self.tray.close_requested())
        self.assertTrue(self.tray.hidden)
        self.window.destroy.assert_not_called()

    def test_failed_install_leaves_normal_close_available(self):
        self.tray.backend = None
        factory = Mock(side_effect=RuntimeError("no tray"))
        self.tray.backend_factory = factory
        with patch("desktop_tray.sys.platform", "win32"), self.assertLogs("desktop_tray", "ERROR"):
            self.tray.start()
        self.assertFalse(self.tray.close_requested())
        self.assertTrue(self.tray.exiting)
        self.backend.hide_window.assert_not_called()

    def test_shutdown_is_not_intercepted(self):
        self.assertFalse(self.tray.close_requested(user_closing=False))
        self.api.stop_tasks.assert_called_once()
        self.api.treehouse_stop.assert_called_once()
        self.backend.hide_window.assert_not_called()

    def test_exit_stops_workers_and_destroys_window_once(self):
        destroyed = threading.Event()
        self.window.destroy.side_effect = destroyed.set
        self.tray.exit()
        self.assertTrue(destroyed.wait(1))
        self.tray.exit()
        self.assertTrue(self.tray.exiting)
        self.api.stop_tasks.assert_called_once()
        self.api.treehouse_stop.assert_called_once()
        self.window.destroy.assert_called_once()
        self.assertFalse(self.tray.close_requested())

    def test_exit_has_bounded_wait_for_task_workers(self):
        released = threading.Event()
        worker = threading.Thread(target=lambda: released.wait(2), daemon=True)
        worker.start()
        self.api._running_thread = worker
        destroyed = threading.Event()
        self.window.destroy.side_effect = destroyed.set
        try:
            self.tray.exit()
            self.assertTrue(destroyed.wait(1))
            self.assertTrue(worker.is_alive())
        finally:
            released.set()
            worker.join(1)

    def test_closed_disposes_tray(self):
        self.tray.closed()
        self.backend.dispose.assert_called_once()
        self.assertTrue(self.tray.exiting)

    def test_installed_tray_is_not_reinstalled(self):
        self.tray.backend_factory = Mock()
        with patch("desktop_tray.sys.platform", "win32"):
            self.tray.start()
        self.tray.backend_factory.assert_not_called()

    def test_task_thread_cannot_keep_process_alive_after_exit(self):
        from gui_main import Api
        api = Api.__new__(Api)
        api._chaoxing = object()
        api._running_thread = None
        api._stop_event = threading.Event()
        released = threading.Event()
        api._run_tasks_thread = lambda ids: released.wait(2)
        try:
            self.assertTrue(api.start_tasks('["100"]')["success"])
            self.assertTrue(api._running_thread.daemon)
        finally:
            released.set()
            if api._running_thread:
                api._running_thread.join(1)


if __name__ == "__main__":
    unittest.main()
