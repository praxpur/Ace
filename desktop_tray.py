"""Keep the desktop window and its workers alive while it is in the Windows tray."""
import logging
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class DesktopTray:
    def __init__(self, window, api, icon_path, backend_factory=None, shutdown_timeout=5.0):
        self.window = window
        self.api = api
        self.icon_path = Path(icon_path)
        self.backend_factory = backend_factory or WinFormsTray
        self.backend = None
        self.exiting = False
        self.hidden = False
        self.notified = False
        self.shutdown_timeout = shutdown_timeout
        self._lock = threading.Lock()

    def start(self):
        if sys.platform != "win32" or self.backend is not None or self.exiting:
            return
        try:
            self.backend_factory(self).install()
        except Exception:
            # Never intercept closing until a usable tray icon exists.
            logger.exception("系统托盘初始化失败，窗口仍可正常退出")

    def hide(self):
        if self.backend is None or self.exiting:
            return

        def apply():
            if self.exiting:
                return
            self.backend.hide_window()
            self.hidden = True
            if not self.notified:
                self.notified = True
                try:
                    self.backend.notify()
                except Exception:
                    logger.debug("系统未显示托盘提示", exc_info=True)

        self.backend.dispatch(apply)

    def show(self):
        if self.backend is None or self.exiting:
            return

        def apply():
            if self.exiting:
                return
            self.backend.show_window()
            self.hidden = False

        self.backend.dispatch(apply)

    def close_requested(self, user_closing=True):
        """Return True only when closing should be cancelled in favour of hiding."""
        if self.backend is not None and not self.exiting and user_closing:
            self.hide()
            return True
        self.exiting = True
        self._stop_workers()
        return False

    def _stop_workers(self):
        for stop in (self.api.stop_tasks, self.api.treehouse_stop):
            try:
                stop()
            except Exception:
                logger.exception("退出时停止后台任务失败")

    def exit(self):
        with self._lock:
            if self.exiting:
                return
            self.exiting = True
        if self.backend is not None:
            self.backend.dispatch(self.backend.mark_exiting)
        self._stop_workers()

        def finish():
            # Let Playwright close Chromium and let task workers observe cancellation.
            deadline = time.monotonic() + self.shutdown_timeout
            workers = (getattr(self.api, "_running_thread", None),
                       getattr(getattr(self.api, "_treehouse", None), "worker", None))
            for worker in workers:
                if worker is not None and worker is not threading.current_thread() and worker.is_alive():
                    worker.join(max(0.0, deadline - time.monotonic()))
            try:
                self.window.destroy()
            except Exception:
                logger.exception("关闭主窗口失败")

        threading.Thread(target=finish, name="tray-shutdown", daemon=True).start()

    def closed(self):
        self.exiting = True
        self._stop_workers()
        if self.backend is not None:
            self.backend.dispatch(self.backend.dispose)


class WinFormsTray:
    """Use PyWebView's existing WinForms message loop; no second GUI toolkit."""
    def __init__(self, controller):
        self.controller = controller
        self.form = controller.window.native
        self.icon = None
        self.menu = None
        self.notify_icon = None
        self._restored_state = None

    def dispatch(self, callback):
        from System import Action
        if self.form.IsDisposed:
            return
        if self.form.InvokeRequired:
            self.form.BeginInvoke(Action(callback))
        else:
            callback()

    def install(self):
        self.dispatch(self._install)

    def _install(self):
        from System.Drawing import Icon
        from System.Windows.Forms import ContextMenuStrip, NotifyIcon, ToolStripMenuItem, ToolStripSeparator
        if self.controller.backend is not None or self.controller.exiting:
            return
        try:
            self.icon = Icon(str(self.controller.icon_path))
            self.menu = ContextMenuStrip()
            self.show_item = ToolStripMenuItem("显示主窗口")
            self.hide_item = ToolStripMenuItem("隐藏到托盘")
            self.exit_item = ToolStripMenuItem("退出分刷酱")
            self.show_item.Click += self._show
            self.hide_item.Click += self._hide
            self.exit_item.Click += self._exit
            for item in (self.show_item, self.hide_item, ToolStripSeparator(), self.exit_item):
                self.menu.Items.Add(item)
            self.notify_icon = NotifyIcon()
            self.notify_icon.Icon = self.icon
            self.notify_icon.Text = "分刷酱 Ace · 双击显示主窗口"
            self.notify_icon.ContextMenuStrip = self.menu
            self.notify_icon.DoubleClick += self._show
            self.notify_icon.Visible = True
            self.form.FormClosing += self._closing
            self.form.Resize += self._resize
            self.form.FormClosed += self._closed
            self.controller.backend = self
            from System.Windows.Forms import FormWindowState
            if self.form.WindowState != FormWindowState.Minimized:
                self._restored_state = self.form.WindowState
        except Exception:
            self.dispose()
            logger.exception("系统托盘初始化失败，窗口仍可正常退出")

    def _show(self, *_):
        self.controller.show()

    def _hide(self, *_):
        self.controller.hide()

    def _exit(self, *_):
        self.controller.exit()

    def _closing(self, sender, args):
        from System.Windows.Forms import CloseReason
        if args.Cancel:
            return
        args.Cancel = self.controller.close_requested(args.CloseReason == CloseReason.UserClosing)

    def _resize(self, *_):
        from System.Windows.Forms import FormWindowState
        if self.form.WindowState == FormWindowState.Minimized:
            self.controller.hide()
        else:
            self._restored_state = self.form.WindowState

    def _closed(self, *_):
        # FormClosed runs on the UI thread, before the WinForms loop is destroyed.
        self.dispose()

    def hide_window(self):
        self.form.Hide()

    def show_window(self):
        from System.Windows.Forms import FormWindowState
        state = self._restored_state or FormWindowState.Normal
        self.form.WindowState = state
        self.form.Show()
        self.form.BringToFront()
        self.form.Activate()

    def notify(self):
        self.notify_icon.BalloonTipTitle = "分刷酱 Ace 仍在后台运行"
        self.notify_icon.BalloonTipText = "课程任务会继续运行。双击托盘图标恢复窗口，右键菜单可退出程序。"
        self.notify_icon.ShowBalloonTip(3000)

    def mark_exiting(self):
        self.notify_icon.Text = "分刷酱 Ace · 正在停止任务并退出"
        for item in (self.show_item, self.hide_item, self.exit_item):
            item.Enabled = False

    def dispose(self):
        if self.notify_icon is not None:
            self.notify_icon.Visible = False
            self.notify_icon.Dispose()
            self.notify_icon = None
        if self.menu is not None:
            self.menu.Dispose()
            self.menu = None
        if self.icon is not None:
            self.icon.Dispose()
            self.icon = None
