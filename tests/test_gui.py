import os
import gc
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from treehouse.controller import JobController
from treehouse.errors import UserCancelled
from treehouse.models import Choice, Event, Outcome, Phase


class SuccessWorkflow:
    def __init__(self, settings, choose, emit, token):
        self.choose, self.emit, self.token = choose, emit, token

    def run(self):
        try:
            self.emit(Event("phase", {"phase": Phase.WAITING_LOGIN.value, "message": "等待测试登录"}))
            self.choose("课程", [Choice("course", "新中国史")], self.token)
            self.choose("视频", [Choice("video", "绪论.mp4")], self.token)
            self.emit(Event("progress", {"current": 1, "duration": 2, "percent": 50}))
            return Outcome("complete", "测试播放完成", "")
        except UserCancelled as error:
            return Outcome("cancelled", str(error), "")


class ErrorWorkflow:
    def __init__(self, settings, choose, emit, token):
        pass

    def run(self):
        return Outcome("error", "测试播放器错误", "")


@unittest.skipUnless(os.getenv("TREE_RUN_GUI_TESTS") == "1", "use --gui")
class GuiTests(unittest.TestCase):
    def setUp(self):
        from treehouse.ui import CourseVideoApp
        # Exercise our own widgets in-process, without OS input or user interaction.
        self.grab_patch = patch("tkinter.Toplevel.grab_set", return_value=None)
        self.grab_patch.start()
        self.preferences = tempfile.TemporaryDirectory()
        self.addCleanup(self.preferences.cleanup)
        self.preferences_path = Path(self.preferences.name) / "appearance.json"
        self.app = CourseVideoApp(JobController(SuccessWorkflow), preferences_path=self.preferences_path,
                                  dpi=96, default_state_path=Path(self.preferences.name) / "auth.json")
        self.app.withdraw()
        self.app.update_idletasks()
        self.callback_errors = []
        errors = self.callback_errors
        self.app.report_callback_exception = lambda *args: errors.append(args)

    def tearDown(self):
        self.app.controller.stop()
        if self.app.controller.worker:
            self.app.controller.worker.join(1)
        self.app.destroy()
        self.app = None
        gc.collect()
        self.grab_patch.stop()
        self.assertEqual(self.callback_errors, [])

    def pump_until(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.update()
            if condition():
                return
            time.sleep(0.01)
        self.fail("GUI condition timed out")

    def select(self):
        self.pump_until(lambda: self.app.dialog is not None)
        if not self.app._selected_keys():
            self.app._select_visible()
        self.app._confirm_selection()

    def test_widgets_and_complete_selection_flow(self):
        self.app.start_button.invoke()
        self.select()
        self.select()
        self.pump_until(lambda: self.app.status_var.get() == "播放完成")
        self.assertEqual(str(self.app.start_button["state"]), "normal")
        self.assertEqual(self.app.progress["value"], 100)
        self.assertEqual(self.app.message_var.get(), "测试播放完成")

    def test_cancel_selection_keeps_main_window(self):
        self.app.start_button.invoke()
        self.pump_until(lambda: self.app.dialog is not None)
        self.app._cancel_selection()
        self.pump_until(lambda: self.app.status_var.get() == "已停止")
        self.assertTrue(self.app.winfo_exists())
        self.assertIsNone(self.app.dialog)

    def test_stop_during_selection_unblocks_worker(self):
        self.app.start_button.invoke()
        self.pump_until(lambda: self.app.dialog is not None)
        self.app.stop_button.invoke()
        self.pump_until(lambda: not self.app.controller.running)
        self.pump_until(lambda: self.app.status_var.get() == "已停止")
        self.assertIsNone(self.app.dialog)

    def test_worker_error_stays_visible_and_allows_restart(self):
        self.app.controller = JobController(ErrorWorkflow)
        self.app.start_button.invoke()
        self.pump_until(lambda: self.app.status_var.get() == "运行失败")
        self.assertIn("测试播放器错误", self.app.message_var.get())
        self.assertTrue(self.app.winfo_exists())
        self.assertEqual(str(self.app.start_button["state"]), "normal")

    def test_invalid_settings_do_not_start_worker(self):
        self.app.login_wait_var.set("nan")
        self.app.start_button.invoke()
        self.assertEqual(self.app.status_var.get(), "设置有误")
        self.assertFalse(self.app.controller.running)

    def test_stale_events_cannot_change_new_run(self):
        self.app.run_id = "new"
        self.app.controller.events.put(("old", Event("phase", {
            "phase": Phase.ERROR.value, "message": "过期事件"
        })))
        self.app._poll()
        self.assertEqual(self.app.status_var.get(), "就绪")

    def test_nonfinite_progress_does_not_crash_ui(self):
        self.app.run_id = "new"
        self.app.controller.events.put(("new", Event("progress", {
            "current": float("nan"), "duration": float("inf"), "percent": float("nan")
        })))
        self.app._poll()
        self.assertEqual(self.app.progress_var.get(), "正在加载媒体信息")
        self.assertEqual(self.app.progress["value"], 0)

    def test_default_state_path_is_prefilled_without_blocking_first_login(self):
        self.assertEqual(self.app.state_var.get(), str(self.app.default_state_path))
        self.assertIsNone(self.app._settings().state_path)
        self.app.headless_var.set(True)
        with self.assertRaisesRegex(Exception, "尚未生成登录态"):
            self.app._settings()

    def test_existing_default_state_and_selected_speed_are_used(self):
        self.app.default_state_path.write_text('{"cookies": [], "origins": []}')
        self.app.speed_var.set("1.5×")
        settings = self.app._settings()
        self.assertEqual(settings.state_path, self.app.default_state_path)
        self.assertEqual(settings.playback_rate, 1.5)

    def test_direct_connection_is_used_and_saved_when_starting(self):
        from treehouse.network import CONNECTION_LABELS, load_connection_mode
        self.app.connection_var.set(CONNECTION_LABELS['direct'])
        self.assertEqual(self.app._settings().connection_mode, 'direct')
        self.app.start_button.invoke()
        self.assertEqual(load_connection_mode(self.app.connection_path), 'direct')
        self.select()
        self.select()
        self.pump_until(lambda: self.app.status_var.get() == '播放完成')

    def test_selection_is_inside_main_window_without_toplevel(self):
        import tkinter as tk
        self.app._show_selection({"request_id": "inline", "title": "课程", "multiple": True,
                                  "choices": [{"key": "a", "label": "新中国史"}]})
        self.assertEqual(self.app.current_view, "catalog")
        self.assertIs(self.app.selection_list.winfo_toplevel(), self.app)
        self.assertFalse(any(isinstance(widget, tk.Toplevel) for widget in self.app.winfo_children()))

    def test_inline_selection_does_not_block_settings_scroll(self):
        self.app.deiconify()
        self.app._show_selection({"request_id": "inline", "title": "课程", "multiple": True,
                                  "choices": [{"key": "a", "label": "新中国史"}]})
        self.app._show("settings")
        self.app.geometry("700x560+0+0")
        self.app.update()
        before = self.app.settings_scroll.canvas.yview()[0]
        self.app._scroll_settings(SimpleNamespace(widget=self.app.url_entry, delta=-120))
        self.app.update_idletasks()
        self.assertGreater(self.app.settings_scroll.canvas.yview()[0], before)
        self.assertEqual(self.app.request_id, "inline")

    def test_failed_task_retains_courses_but_rescan_requires_selection(self):
        rows = [{"key": "old:0", "label": "新中国史", "detail": "2026"},
                {"key": "old:1", "label": "新中国史", "detail": "2025"}]
        self.app._show_selection({"request_id": "first", "title": "课程", "multiple": True,
                                  "choices": rows})
        self.app._clear_selection()
        self.app.selection_list.selection_set(1)
        self.app._selection_changed()
        self.app.run_id = "failed"
        self.app.controller.events.put(("failed", Event("finished", {
            "status": "error", "message": "测试资源加载失败", "diagnostic_dir": ""})))
        self.app._poll()
        self.assertEqual(self.app.course_panel.rows, rows)
        self.assertEqual(self.app.course_panel.selected(), ["old:1"])
        self.assertIsNone(self.app.request_id)
        fresh = [{**rows[1], "key": "new:0"}, {**rows[0], "key": "new:1"}]
        self.app._show_selection({"request_id": "retry", "title": "课程", "multiple": True,
                                  "choices": fresh})
        self.assertEqual(self.app._selected_keys(), [])

    def test_inline_buttons_fit_and_have_no_surface_rectangle(self):
        self.app.deiconify()
        data = {"request_id": "layout", "title": "课程", "multiple": True,
                "choices": [{"key": "a", "label": "新中国史"}]}
        self.app._show_selection(data)
        for dpi in (96, 144, 192):
            self.app._dpi = dpi
            with patch("treehouse.ui_layout.work_area", return_value=(0, 0, 1200, 900)):
                self.app._rescale()
            self.app.geometry("1200x900+0+0")
            self.app.update()
            for panel in (self.app.course_panel, self.app.video_panel):
                if not panel.winfo_ismapped():
                    continue
                left, right = panel.all_button, panel.clear_button
                self.assertLessEqual(left.winfo_rootx() + left.winfo_width(), right.winfo_rootx())
                self.assertLessEqual(right.winfo_rootx() + right.winfo_width(),
                                     panel.winfo_rootx() + panel.winfo_width())
            cancel, confirm = self.app.cancel_selection_button, self.app.confirm_button
            self.assertLessEqual(cancel.winfo_rootx() + cancel.winfo_width(), confirm.winfo_rootx())
            self.assertLessEqual(confirm.winfo_rooty() + confirm.winfo_height(),
                                 self.app.winfo_rooty() + self.app.winfo_height())
        for mode in ("light", "dark"):
            self.app.set_theme(mode)
            for button in (self.app.start_button, self.app.confirm_button,
                           self.app.course_panel.all_button, self.app.nav_buttons["catalog"]):
                expected = getattr(self.app.theme.palette, button.surface_role)
                for state in ((), ("active",), ("pressed",), ("disabled",), ("focus",)):
                    self.assertEqual(self.app.theme.style.lookup(button.cget("style"), "background", state),
                                     expected)

    def test_theme_switch_updates_main_log_and_open_dialog(self):
        self.app.start_button.invoke()
        self.pump_until(lambda: self.app.dialog is not None)
        request = self.app.request_id
        self.app.set_theme("dark")
        palette = self.app.theme.palette
        self.assertEqual(self.app.cget("bg"), palette.surface)
        self.assertEqual(self.app.log_view.cget("bg"), palette.surface_low)
        self.assertEqual(self.app.selection_list.cget("bg"), palette.surface_low)
        self.assertEqual(self.app.request_id, request)
        self.app.set_theme("light")
        self.assertEqual(self.app.theme.mode, "light")
        self.assertEqual(self.app.request_id, request)

    def test_zoom_preserves_task_dialog_search_and_logs(self):
        self.app._append_log("缩放前的日志")
        self.app.start_button.invoke()
        self.pump_until(lambda: self.app.dialog is not None)
        request, run_id = self.app.request_id, self.app.run_id
        self.app._select_visible()
        self.app.search_var.set("新中国")
        self.app.set_zoom(1.5)
        self.assertEqual(self.app.request_id, request)
        self.assertEqual(self.app.run_id, run_id)
        self.assertEqual(self.app.search_var.get(), "新中国")
        self.assertEqual(self.app._selected_key(), "course")
        self.assertIn("缩放前的日志", self.app.log_view.get("1.0", "end"))
        self.assertEqual(str(self.app.start_button["state"]), "disabled")
        self.app._confirm_selection()
        self.select()
        self.pump_until(lambda: self.app.status_var.get() == "播放完成")

    def test_filter_maps_to_original_key_and_empty_disables_confirm(self):
        choices = [{"key": "one", "label": "课程", "detail": "2025"},
                   {"key": "two", "label": "课程", "detail": "2026"}]
        self.app._show_selection({"request_id": "test", "title": "课程", "choices": choices})
        self.app.search_var.set("missing")
        self.assertEqual(str(self.app.confirm_button["state"]), "disabled")
        self.app.search_var.set("2026")
        self.assertEqual(self.app._selected_key(), "two")
        with patch.object(self.app.controller, "resolve", return_value=True) as resolve:
            self.app._confirm_selection()
        resolve.assert_called_once_with("test", "two")

    def test_preferences_write_failure_keeps_ui_usable(self):
        with patch("treehouse.appearance.Appearance.save", side_effect=OSError("test denied")):
            self.app.set_theme("dark")
        self.assertEqual(self.app.theme.mode, "dark")
        self.app._flush_logs()
        self.assertIn("无法保存偏好", self.app.log_view.get("1.0", "end"))

    def test_dpi_layout_has_visible_footer_and_scrollable_form(self):
        # Physical 1200x900 work area at 100/125/150/200%, on the real Tk layout engine.
        self.app.deiconify()
        for dpi in (96, 120, 144, 192):
            with self.subTest(dpi=dpi):
                self.app._dpi = dpi
                with patch("treehouse.ui_layout.work_area", return_value=(0, 0, 1200, 900)):
                    self.app._rescale()
                self.app.geometry("1200x900+0+0")
                self.app.update()
                self.assertEqual(self.app.theme.dp(40), round(40 * dpi / 96))
                button = self.app.start_button
                bottom = button.winfo_rooty() + button.winfo_height()
                self.assertLessEqual(bottom, self.app.winfo_rooty() + self.app.winfo_height())
                self.assertGreater(button.winfo_width(), self.app.theme.dp(200))
                self.assertGreater(self.app.url_entry.winfo_width(), self.app.theme.dp(180))
                self.app.settings_scroll.ensure_visible(self.app.remember_check)
                self.app.update_idletasks()
                check = self.app.remember_check
                viewport = self.app.settings_scroll.canvas
                self.assertGreaterEqual(check.winfo_rooty(), viewport.winfo_rooty())
                self.assertLessEqual(check.winfo_rooty() + check.winfo_height(),
                                     viewport.winfo_rooty() + viewport.winfo_height())
                self.app._show("monitor")
                self.app.update_idletasks()
                self.assertLessEqual(self.app.stop_button.winfo_rooty() + self.app.stop_button.winfo_height(),
                                     self.app.winfo_rooty() + self.app.winfo_height())
                self.app._show("settings")

    def test_dpi_watcher_rescales_without_resetting_progress(self):
        self.app.progress.configure(value=37)
        self.app.url_var.set("https://example.com/course")
        with patch("treehouse.ui_layout.window_dpi", return_value=192):
            self.app._display_watch()
        self.assertEqual(self.app.theme.scale, 2)
        self.assertEqual(self.app.progress["value"], 37)
        self.assertEqual(self.app.url_var.get(), "https://example.com/course")

    def test_long_course_and_error_message_do_not_hide_stop(self):
        self.app.deiconify()
        self.app.geometry("700x560+0+0")
        self.app.course_var.set("很长的课程名称" * 12)
        self.app.message_var.set("测试长错误说明，需要能够滚动阅读。" * 20)
        self.app._show("monitor")
        self.app.update()
        self.assertLessEqual(self.app.stop_button.winfo_rooty() + self.app.stop_button.winfo_height(),
                             self.app.winfo_rooty() + self.app.winfo_height())
        self.assertFalse(hasattr(self.app, "monitor_scroll"))
        self.assertGreater(self.app.log_view.winfo_height(), 25)

    def test_narrow_window_uses_compact_navigation(self):
        self.app.deiconify()
        self.app.geometry("700x560+0+0")
        self.app.update()
        self.assertTrue(self.app.compact)
        self.assertEqual(self.app.nav_buttons["settings"].cget("text"), "学习")
        self.assertGreater(self.app.settings_scroll.canvas.winfo_height(), 100)

    def test_log_wheel_does_not_scroll_surrounding_page(self):
        self.app._show("monitor")
        with patch.object(self.app.settings_scroll, "scroll") as scroll:
            self.app._scroll_settings(SimpleNamespace(widget=self.app.log_view, delta=-120))
        scroll.assert_not_called()

    def test_multi_selection_survives_search_and_zoom(self):
        data = {"request_id": "multi", "title": "课程", "multiple": True, "choices": [
            {"key": "a", "label": "课程一"}, {"key": "b", "label": "课程二"},
            {"key": "c", "label": "课程三"}]}
        self.app._show_selection(data)
        self.app.selection_list.selection_set(0)
        self.app._selection_changed()
        self.app.search_var.set("二")
        self.app._select_visible()
        self.assertEqual(self.app._selected_keys(), ["a", "b"])
        self.app.set_zoom(1.15)
        self.assertEqual(self.app._selected_keys(), ["a", "b"])
        self.app.search_var.set("无匹配")
        with patch.object(self.app.controller, "resolve", return_value=True) as resolve:
            self.app._confirm_selection()
        resolve.assert_called_once_with("multi", ["a", "b"])

    def test_clear_multi_selection_disables_confirm(self):
        self.app._show_selection({"request_id": "multi", "title": "视频", "multiple": True,
                                  "choices": [{"key": "a", "label": "视频.mp4"}]})
        self.app._clear_selection()
        self.assertEqual(self.app._selected_keys(), [])
        self.assertEqual(str(self.app.confirm_button["state"]), "disabled")

    def test_course_selection_never_shows_cached_video_checkboxes(self):
        self.app.deiconify()
        self.app.video_panel.load({'choices': [{'key': 'stale', 'label': '旧视频'}], 'selected': ['stale']})
        self.app._show_selection({'request_id': 'courses', 'title': '课程', 'multiple': True,
                                  'choices': [{'key': 'a', 'label': '课程一'}]})
        self.app.update()
        self.assertTrue(self.app.course_surface.winfo_ismapped())
        self.assertFalse(self.app.video_surface.winfo_ismapped())
        self.assertEqual(self.app._selected_keys(), [])
        self.assertEqual(str(self.app.confirm_button['state']), 'disabled')
        self.assertIn('扫描', self.app.confirm_button.cget('text'))
        self.assertNotIn('继续', self.app.confirm_button.cget('text'))

    def test_course_rows_toggle_with_single_click_without_ctrl(self):
        self.app.deiconify()
        self.app.geometry('1000x700+0+0')
        self.app._show_selection({'request_id': 'courses', 'title': '课程', 'multiple': True,
                                  'choices': [{'key': 'a', 'label': '课程一'},
                                              {'key': 'b', 'label': '课程二'}]})
        self.app.update()
        tree = self.app.course_panel.listbox
        for iid in ('0', '1'):
            x, y, width, height = tree.bbox(iid)
            tree.event_generate('<Button-1>', x=x + 10, y=y + height // 2)
            self.app.update()
        self.assertEqual(self.app._selected_keys(), ['a', 'b'])
        x, y, width, height = tree.bbox('0')
        tree.event_generate('<Button-1>', x=x + 10, y=y + height // 2)
        self.app.update()
        self.assertEqual(self.app._selected_keys(), ['b'])

    def test_course_rows_support_keyboard_navigation_and_selection(self):
        self.app.deiconify()
        self.app.geometry('1000x700+0+0')
        self.app._show_selection({'request_id': 'courses', 'title': '课程', 'multiple': True,
                                  'choices': [{'key': 'a', 'label': '课程一'},
                                              {'key': 'b', 'label': '课程二'}]})
        self.app.update()
        tree = self.app.course_panel.listbox
        tree.focus_force()
        tree.focus('0')
        self.app.update()
        tree.event_generate('<KeyPress-space>')
        self.app.update()
        tree.event_generate('<KeyPress-Down>')
        tree.event_generate('<KeyPress-space>')
        self.app.update()
        self.assertEqual(self.app._selected_keys(), ['a', 'b'])

    def test_loading_playback_does_not_return_step_indicator_to_connection(self):
        self.app.selection_stage = 'playing'
        self.app._last_phase = Phase.WAITING_PAGE.value
        self.app._update_step()
        self.assertIn('● 播放', self.app.step_var.get())
        self.assertNotIn('● 连接', self.app.step_var.get())

    def test_rescan_does_not_automatically_reselect_courses(self):
        courses = [{'key': 'old:a', 'label': '课程甲', 'detail': '共享课'},
                   {'key': 'old:b', 'label': '课程乙', 'detail': 'AI智课'}]
        self.app._show_selection({'request_id': 'courses', 'title': '课程', 'multiple': True,
                                  'choices': courses})
        self.app._select_visible()
        self.app._dismiss_dialog()
        groups = [{'key': 'scan:0', 'course': courses[0], 'videos': [
            {'key': 'plan:0', 'label': '视频甲', 'detail': '', 'signature': 'a'}]},
                  {'key': 'scan:1', 'course': courses[1], 'videos': [
            {'key': 'plan:1', 'label': '视频乙', 'detail': '', 'signature': 'b'}]}]
        self.app.draft.load(groups)
        self.app._plan_ready = True
        self.app._show_selection({'request_id': 'videos', 'title': '视频', 'multiple': True,
                                  'choices': [g['videos'][0] for g in groups]})
        self.app._dismiss_dialog()
        fresh = [{**courses[1], 'key': 'new:b'}, {**courses[0], 'key': 'new:a'}]
        self.app._show_selection({'request_id': 'rescan', 'title': '课程', 'multiple': True,
                                  'choices': fresh})
        self.assertEqual(self.app._selected_keys(), [])

    def test_select_unfinished_skips_completed_and_unknown_but_allows_manual_choice(self):
        courses = [{'key': 'a', 'label': '课程'}]
        videos = [{'key': 'done', 'label': '已看', 'detail': '', 'signature': 'a', 'completed': True},
                  {'key': 'partial', 'label': '未看完', 'detail': '', 'signature': 'b', 'completed': False},
                  {'key': 'unknown', 'label': '未知', 'detail': '', 'signature': 'c', 'completed': None}]
        self.app.draft.load([{'key': 'scan:0', 'course': courses[0], 'videos': videos}])
        self.app._plan_ready = True
        self.app._show_selection({'request_id': 'videos', 'title': '视频', 'multiple': True,
                                  'choices': videos})
        self.assertEqual(self.app._selected_keys(), [])
        self.app.video_panel.unfinished_button.invoke()
        self.assertEqual(self.app._selected_keys(), ['partial'])
        self.app.video_panel.listbox.selection_set(0)
        self.app.video_panel.changed()
        self.assertEqual(self.app._selected_keys(), ['done', 'partial'])
        self.app.set_zoom(1.15)
        self.assertEqual(self.app._selected_keys(), ['done', 'partial'])

    def test_video_bulk_buttons_fit_at_high_dpi(self):
        self.app.deiconify()
        videos = [{'key': 'v', 'label': '视频', 'detail': '',
                   'signature': 'v', 'completed': False}]
        self.app.draft.load([{'key': 'scan:0', 'course': {'label': '课程'}, 'videos': videos}])
        self.app._plan_ready = True
        self.app._show_selection({'request_id': 'videos', 'title': '视频', 'multiple': True,
                                  'choices': videos})
        for dpi in (96, 144, 192):
            self.app._dpi = dpi
            with patch('treehouse.ui_layout.work_area', return_value=(0, 0, 1200, 900)):
                self.app._rescale()
            self.app.geometry('1200x900+0+0')
            self.app.update()
            panel = self.app.video_panel
            buttons = [panel.all_button, panel.unfinished_button, panel.clear_button]
            for left, right in zip(buttons, buttons[1:]):
                self.assertLessEqual(left.winfo_rootx() + left.winfo_width(), right.winfo_rootx())
            self.assertLessEqual(buttons[-1].winfo_rootx() + buttons[-1].winfo_width(),
                                 panel.winfo_rootx() + panel.winfo_width())
            self.assertLessEqual(self.app.confirm_button.winfo_rooty() + self.app.confirm_button.winfo_height(),
                                 self.app.winfo_rooty() + self.app.winfo_height())

    @unittest.skipUnless(os.getenv('TREE_RUN_BROWSER_TESTS') == '1', 'use --browser as well')
    def test_all_courses_scanned_before_one_final_playback_confirmation(self):
        from treehouse.adapter import ZhihuishuAdapter
        from treehouse.workflow import Workflow
        from tests.fixture_server import CENTER, FixtureServer
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            events = []
            def factory(settings, choose, emit, token):
                settings = replace(settings, start_url=server.origin + CENTER + '?case=batch&mode=same',
                                   headless=True, login_timeout=8, page_timeout=5, video_timeout=8,
                                   stall_timeout=4, poll_interval=.05, artifacts_dir=Path(folder))
                def record(event):
                    events.append(event)
                    emit(event)
                return Workflow(settings, choose, record, token,
                                ZhihuishuAdapter(True, .05, server.profile))
            self.app.controller = JobController(factory)
            self.app.start_button.invoke()
            self.pump_until(lambda: self.app.request_id is not None, 8)
            self.app._select_visible()
            self.app._confirm_selection()
            self.pump_until(lambda: self.app.request_id is not None, 10)
            self.assertEqual(len(self.app.draft.groups), 2)
            self.assertEqual(self.app._selected_keys(), [])
            self.assertEqual(str(self.app.confirm_button['state']), 'disabled')
            self.assertFalse(any(e.kind in ('queue', 'progress') for e in events))
            self.app.video_panel.listbox.selection_set(0)
            self.app.video_panel.changed()
            first = self.app._selected_keys()
            self.app.course_panel.listbox.selection_clear(0, 'end')
            self.app.course_panel.listbox.selection_set(1)
            self.app.course_panel.changed()
            self.app.video_panel.listbox.selection_set(0)
            self.app.video_panel.changed()
            self.assertEqual(len(self.app._selected_keys()), 2)
            self.assertIn(first[0], self.app._selected_keys())
            self.app.set_zoom(1.15)
            self.assertEqual(len(self.app._selected_keys()), 2)
            self.assertIn('开始播放', self.app.confirm_button.cget('text'))
            self.app._confirm_selection()
            self.pump_until(lambda: not self.app.controller.running
                            and self.app.status_var.get() == '播放完成', 20)
            phases = [e.data['phase'] for e in events if e.kind == 'phase']
            self.assertEqual(phases.count(Phase.CHOOSING_COURSE.value), 1)
            self.assertEqual(phases.count(Phase.CHOOSING_VIDEO.value), 1)
            self.assertEqual(sum(e.kind == 'progress' and e.data['ended'] for e in events), 2)

    def test_log_scrollbar_is_single_and_only_visible_when_needed(self):
        self.app.deiconify()
        self.app._show("monitor")
        self.app.update()
        self.assertFalse(self.app.log_scrollbar.winfo_ismapped())
        for index in range(250):
            self.app._append_log(f"日志 {index}")
        self.app._flush_logs()
        self.app.update()
        self.assertTrue(self.app.log_scrollbar.winfo_ismapped())
        self.assertFalse(hasattr(self.app, "monitor_scroll"))
        self.app.log_view.yview_moveto(0)
        self.app.update_idletasks()
        before = self.app.log_view.yview()[0]
        self.app._append_log("后续日志")
        self.app._flush_logs()
        self.app.update_idletasks()
        self.assertLessEqual(abs(self.app.log_view.yview()[0] - before), .01)

    def test_idle_layout_settles_and_keeps_timers_responsive(self):
        self.app.deiconify()
        self.app.update()
        ticks = []
        self.app.after(60, lambda: ticks.append(time.monotonic()))
        started = time.monotonic()
        self.pump_until(lambda: bool(ticks), timeout=1)
        self.assertLess(ticks[0] - started, .5)

    @unittest.skipUnless(os.name == "nt", "Windows caption attributes")
    def test_windows_caption_follows_theme_and_keeps_native_controls(self):
        import ctypes
        from ctypes import wintypes
        self.app.deiconify()
        self.app.update()
        self.app.set_theme("dark")
        if not self.app.caption_result.get(35):
            self.skipTest("Custom caption color requires Windows 11")
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = user32.GetAncestor(self.app.winfo_id(), 2)
        # Caption colors are setter-only DWM attributes. Inspect the real
        # window style to verify that native caption controls remain enabled.
        getter = user32.GetWindowLongW
        getter.argtypes, getter.restype = [wintypes.HWND, ctypes.c_int], ctypes.c_long
        style = getter(hwnd, -16)
        self.assertEqual(style & 0x000B0000, 0x000B0000)  # min/max boxes and system menu
        self.app.iconify()
        self.app.update()
        self.assertEqual(self.app.state(), "iconic")
        self.app.deiconify()
        self.app.update()
        self.assertEqual(self.app.state(), "normal")
        self.app.state("zoomed")
        self.app.update()
        self.assertEqual(self.app.state(), "zoomed")
        self.app.state("normal")

    @unittest.skipUnless(os.getenv("TREE_RUN_BROWSER_TESTS") == "1", "use --browser as well")
    def test_gui_with_real_browser_and_natural_video_end(self):
        from treehouse.adapter import ZhihuishuAdapter
        from treehouse.workflow import Workflow
        from tests.fixture_server import CENTER, FixtureServer
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            def factory(settings, choose, emit, token):
                settings = replace(
                    settings, start_url=server.origin + CENTER, headless=True,
                    login_timeout=8, page_timeout=5, video_timeout=8,
                    stall_timeout=4, poll_interval=0.05, artifacts_dir=Path(folder),
                )
                return Workflow(settings, choose, emit, token,
                                ZhihuishuAdapter(True, 0.05, server.profile))
            self.app.controller = JobController(factory)
            self.app.start_button.invoke()
            self.select()
            self.select()
            self.pump_until(
                lambda: not self.app.controller.running
                and str(self.app.start_button["state"]) == "normal", 15
            )
            self.assertEqual(self.app.status_var.get(), "播放完成", self.app.message_var.get())
