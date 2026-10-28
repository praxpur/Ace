"""Tk view. Browser objects and widgets never cross the worker boundary."""
import queue
import tkinter as tk
import threading
import traceback
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

from .appearance import Appearance, effective_scale, resolve_theme
from .config import COURSE_CENTER_URL, DEFAULT_STATE_PATH, PROJECT_ROOT, Settings
from .controller import JobController
from .errors import ConfigurationError
from .display import enable_dpi_awareness, window_dpi
from .models import Phase
from .network import CONNECTION_LABELS, load_connection_mode, save_connection_mode
from .player import finite_number
from .selection import PlaybackDraft
from .ui_layout import MaterialView
from .ui_widgets import MaterialTheme

PHASE_LABELS = {
    Phase.STARTING.value: "启动浏览器", Phase.WAITING_PAGE.value: "等待页面渲染",
    Phase.WAITING_LOGIN.value: "等待人工登录 / 验证码",
    Phase.CHOOSING_COURSE.value: "选择课程", Phase.LOADING_RESOURCES.value: "加载课程资源",
    Phase.CHOOSING_VIDEO.value: "选择视频", Phase.LOADING_VIDEO.value: "加载播放器",
    Phase.PLAYING.value: "视频播放中", Phase.COMPLETE.value: "播放完成",
    Phase.CANCELLED.value: "已停止", Phase.ERROR.value: "运行失败",
}


class CourseVideoApp(MaterialView, tk.Tk):
    def __init__(self, controller=None, *, preferences_path=None, dpi=None, default_state_path=None):
        enable_dpi_awareness()
        super().__init__()
        self._owner_thread = threading.get_ident()
        self.title("树屋 | 课程学习助手")
        self.preferences_path = preferences_path or PROJECT_ROOT / ".state" / "appearance.json"
        self.connection_path = self.preferences_path.parent / 'connection.json'
        self.default_state_path = default_state_path or DEFAULT_STATE_PATH
        self.appearance = Appearance.load(self.preferences_path)
        self._dpi = dpi if dpi is not None else window_dpi(self)
        self.theme = MaterialTheme(self, effective_scale(self._dpi, self.appearance.zoom),
                                   resolve_theme(self.appearance.theme))
        self.controller = controller or JobController()
        self.run_id = ""
        self.closing = False
        self.current_view = "settings"
        self._last_phase = ""
        self._poll_job = self._display_job = None
        self._log_job = None
        self._pending_logs = []
        self._selection_data = None
        self.selection_stage = 'idle'
        self.draft = PlaybackDraft()
        self._plan_ready = False
        self._catalog_building = True
        self.course_cache = {"choices": [], "selected": []}
        self.video_caches = {}
        self._current_course_choice = None
        self.active_panel = None
        self.dialog = self.request_id = self.selection_list = None
        self.selection_choices = []
        self.filtered_choices = []
        self._selection_keys = set()
        self.status_var = tk.StringVar(value="就绪")
        self.message_var = tk.StringVar(value="课程和视频将在运行时从页面扫描。")
        self.diagnostic_var = tk.StringVar()
        self.progress_var = tk.StringVar(value="等待开始")
        self.queue_var = tk.StringVar(value="待建立播放队列")
        self._queue_current = None
        self.url_var = tk.StringVar(value=COURSE_CENTER_URL)
        self.login_wait_var = tk.StringVar(value="300")
        self.video_wait_var = tk.StringVar(value="7200")
        self.state_var = tk.StringVar(value=str(self.default_state_path))
        self.state_hint_var = tk.StringVar()
        self.speed_var = tk.StringVar(value="1×")
        self.connection_var = tk.StringVar(
            value=CONNECTION_LABELS[load_connection_mode(self.connection_path)])
        self.headless_var = tk.BooleanVar(value=False)
        self.remember_var = tk.BooleanVar(value=False)
        self.course_var = tk.StringVar(value="尚未选择课程")
        self.video_var = tk.StringVar(value="开始任务后，在扫描到的资源中选择视频。")
        self.search_var = tk.StringVar()
        self.selection_count_var = tk.StringVar()
        self.course_search_var = tk.StringVar()
        self.video_search_var = tk.StringVar()
        self.course_count_var = tk.StringVar()
        self.video_count_var = tk.StringVar()
        self.selection_note_var = tk.StringVar(value="开始任务后会扫描课程，扫描结果将在这里保留。")
        self.step_var = tk.StringVar(value='01 连接账号   /   02 选择课程   /   03 选择视频   /   04 播放')
        self.video_heading_var = tk.StringVar(value='先扫描，再选择视频')
        self.zoom_var = tk.StringVar(value=f"{round(self.appearance.zoom * 100)}%")
        self.scale_var = tk.StringVar()
        self._update_state_hint()
        self._build()
        self._fit_initial_window()
        self.bind("<Configure>", self._responsive_layout, add="+")
        self.bind("<Map>", self._theme_caption, add="+")
        self.bind("<MouseWheel>", self._scroll_settings, add="+")
        self.bind("<Button-4>", self._scroll_settings, add="+")
        self.bind("<Button-5>", self._scroll_settings, add="+")
        self.bind("<FocusIn>", self._focus_settings, add="+")
        self.state_var.trace_add("write", self._update_state_hint)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._poll_job = self.after(100, self._poll)
        # A supplied DPI is a deterministic layout-test override.
        if dpi is None:
            self._display_job = self.after(1500, self._display_watch)

    def _browse_state(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON 登录态", "*.json")])
        if path:
            self.state_var.set(path)

    def _update_state_hint(self, *_):
        raw = self.state_var.get().strip()
        try:
            exists = bool(raw) and Path(raw).expanduser().is_file()
        except (OSError, ValueError):
            exists = False
        self.state_hint_var.set("已找到登录态文件；有效性将在启动时检查。" if exists else (
            "登录后勾选“记住本次登录”，程序会生成默认文件。" if raw else "不使用已有登录态，手动登录。"))

    def _settings(self):
        raw = self.state_var.get().strip()
        state_path = Path(raw).expanduser() if raw else None
        if state_path == self.default_state_path and not state_path.is_file():
            if self.headless_var.get():
                raise ConfigurationError("尚未生成登录态。请先关闭无头运行，勾选“记住本次登录”并登录。")
            state_path = None
        mode = next((key for key, label in CONNECTION_LABELS.items()
                     if label == self.connection_var.get()), None)
        if mode is None:
            raise ConfigurationError('请选择有效的连接方式。')
        return Settings(
            start_url=self.url_var.get().strip(), headless=self.headless_var.get(),
            login_timeout=float(self.login_wait_var.get()),
            video_timeout=float(self.video_wait_var.get()),
            state_path=state_path,
            save_state_path=self.default_state_path if self.remember_var.get() else None,
            playback_rate=float(self.speed_var.get().removesuffix("×")),
            connection_mode=mode,
        ).validate()

    def _start(self):
        if self.controller.running:
            return
        try:
            self._capture_catalog()
            self._plan_ready = False
            self.selection_stage = 'connecting'
            settings = self._settings()
            try:
                save_connection_mode(self.connection_path, settings.connection_mode)
            except OSError:
                self._append_log('连接方式本次仍有效，但无法保存供下次使用。')
            self.run_id = self.controller.start(settings)
        except Exception as error:
            self.message_var.set(f"无法启动：{error}")
            self.status_var.set("设置有误")
            self._last_phase = "error"
            self._color_status()
            self._append_log(self.message_var.get())
            self._catalog_changed()
            self._show("catalog" if self.course_cache["choices"] else "monitor")
            return
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("正在启动")
        self.message_var.set("正在连接账号并读取课程。此阶段不会开始播放。")
        self.diagnostic_var.set("")
        self.progress_var.set("第 1 步 · 连接账号")
        self.progress.configure(value=0)
        self.queue_var.set("待建立播放队列")
        self._queue_current = None
        self.course_var.set("尚未选择课程")
        self.video_var.set("正在等待课程目录。")
        self._last_phase = "starting"
        self._color_status()
        self._show("monitor")
        self._catalog_changed()

    def _poll(self):
        # A manual refresh must not leave a second timer armed.
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
            self._poll_job = None
        deadline = time.perf_counter() + .008
        for _ in range(200):
            if time.perf_counter() > deadline:
                break
            try:
                run_id, event = self.controller.events.get_nowait()
            except queue.Empty:
                break
            if run_id != self.run_id:
                continue
            data = event.data
            if event.kind == "phase":
                self.status_var.set(PHASE_LABELS.get(data["phase"], data["phase"]))
                self.message_var.set(data["message"])
                self._last_phase = data["phase"]
                self._color_status()
                self._update_step()
            elif event.kind == "log":
                self._append_log(data["message"])
            elif event.kind == "session_saved":
                self.state_var.set(data["path"])
                self._update_state_hint()
            elif event.kind == "selected":
                variable = self.course_var if data["category"] == "课程" else self.video_var
                variable.set(data["choice"]["label"])
                if data["category"] == "课程":
                    self._activate_course(data["choice"])
            elif event.kind == 'scan_progress':
                self.selection_stage = 'scanning'
                self.progress_var.set(f"扫描课程 {data['current']} / {data['total']}")
                self.queue_var.set('扫描资源 · 尚未开始播放')
                self.video_var.set(data['message'])
                self.progress.configure(value=100 * data['current'] / data['total']
                                        if 'count' in data else 100 * (data['current'] - 1) / data['total'])
                self._update_step()
            elif event.kind == 'catalog_ready':
                self.draft.load(data['groups'])
                self._plan_ready = True
                self._render_draft()
                self._catalog_changed()
            elif event.kind == "queue":
                self.queue_var.set(f"队列 · 已完成 {data['completed']} / {data['total']}")
                if self._queue_current != data["current"]:
                    self._queue_current = data["current"]
                    self.progress.configure(value=0)
                    self.progress_var.set("等待媒体信息")
            elif event.kind == "progress":
                current, duration = finite_number(data.get("current")), finite_number(data.get("duration"))
                self.progress.configure(value=min(100, finite_number(data.get("percent"))))
                self.progress_var.set(
                    f"{self._format_time(current)} / {self._format_time(duration)}"
                    f" · 实际 {finite_number(data.get('playback_rate'), 1.0) or 1.0:g}×"
                    if duration else "正在加载媒体信息"
                )
            elif event.kind == "selection_request":
                if self.controller.token.cancelled:
                    self.controller.resolve(data["request_id"], None)
                else:
                    self._show_selection(data)
            elif event.kind == "finished":
                self._dismiss_dialog()
                self.selection_stage = 'idle'
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.message_var.set(data["message"])
                self._last_phase = data["status"]
                self._color_status()
                self.status_var.set({
                    "complete": "播放完成", "cancelled": "已停止", "error": "运行失败"
                }.get(data["status"], "已结束"))
                self.diagnostic_var.set(
                    f"诊断目录：{data['diagnostic_dir']}" if data["diagnostic_dir"] else ""
                )
                if data["status"] == "complete":
                    self.progress.configure(value=100)
                self._catalog_changed()
                self._update_step()
                if data["status"] == "error" and self.course_cache["choices"]:
                    self._show("catalog")
        if self.closing and not self.controller.running:
            self.destroy()
            return
        self._flush_logs()
        self._poll_job = self.after(100, self._poll)

    def _course_cache_key(self):
        choice = self._current_course_choice or {}
        return choice.get("label", ""), choice.get("detail", "")

    def _capture_catalog(self):
        if not hasattr(self, "course_panel") or not self.course_panel.winfo_exists():
            return
        if self.selection_stage == 'videos' and self._plan_ready:
            self.draft.update_current(self.video_panel.selected())
        elif not any(row['key'].startswith('scan:') for row in self.course_panel.rows):
            self.course_cache = self.course_panel.export()
            self.video_caches[self._course_cache_key()] = self.video_panel.export()

    def _activate_course(self, choice):
        self._capture_catalog()
        self._current_course_choice = choice
        self._catalog_changed()

    def _selection_aliases(self):
        panel = self.active_panel
        if panel is None:
            return
        self.selection_list = panel.listbox
        self.selection_choices = panel.rows
        self.filtered_choices = panel.visible_rows
        self._selection_keys = panel.keys
        self.search_var = panel.query_var
        self.selection_count_var = panel.count_var

    def _catalog_changed(self):
        if self._catalog_building:
            return
        if self.selection_stage == 'videos' and self._plan_ready:
            self.draft.update_current(self.video_panel.selected())
            browsing = self.course_panel.selected()
            if browsing and browsing[0] != self.draft.current:
                self.draft.current = browsing[0]
                self._load_draft_course()
        self._capture_catalog()
        self._selection_aliases()
        pending = self.request_id is not None
        if pending:
            self.cancel_selection_button.grid()
            self.confirm_button.grid()
            self.retry_button.grid_remove()
            self.logs_button.grid_remove()
            keys = self._selected_keys()
            self.confirm_button.configure(state="normal" if keys else "disabled")
            title = self._selection_data["title"]
            if title == '课程':
                self.confirm_button.configure(text=f'扫描 {len(keys)} 门课的视频')
                self.selection_note_var.set('这里只选择要扫描的课程。扫描完成后，再统一勾选视频。')
            else:
                self.confirm_button.configure(text=f'开始播放 · {len(keys)} 个视频')
                self.selection_note_var.set(
                    f'已选 {self.draft.course_count} 门课程、{len(keys)} 个视频。'
                    '“选未完成”只新增明确未完成项，未知状态需手选；“全选”包含当前结果的所有状态。'
                    if self._plan_ready else '勾选视频，点击“开始播放”后启动队列。')
        else:
            self.cancel_selection_button.grid_remove()
            self.confirm_button.grid_remove()
            self.retry_button.grid()
            self.logs_button.grid()
            running = str(self.start_button["state"]) == "disabled"
            self.retry_button.configure(state="disabled" if running else "normal")
            self.confirm_button.configure(state="disabled")
            self.selection_note_var.set(
                "运行失败。扫描结果和勾选已保留，可查看日志后重试。" if self._last_phase == "error"
                else "上次清单仅供查看。重新连接后可选择课程并更新目录。" if self.course_cache["choices"]
                else "连接账号后，先选择课程，再统一选择视频。")
        self._set_catalog_layout()

    def _load_draft_course(self):
        group = self.draft.current_group
        building = self._catalog_building
        self._catalog_building = True
        self.video_panel.set_enabled(True)
        videos = group['videos'] if group else []
        self.video_panel.set_items(videos, multiple=True,
                                   selected_keys=[v['key'] for v in videos if v['key'] in self.draft.selected])
        self._catalog_building = building
        course = group['course']['label'] if group else '当前课程'
        if videos:
            finished = sum(v.get('completed') is True for v in videos)
            unfinished = sum(v.get('completed') is False for v in videos)
            unknown = len(videos) - finished - unfinished
            self.video_heading_var.set(f'{course} · 已完成 {finished} / 未完成 {unfinished} / 未知 {unknown}')
        else:
            self.video_heading_var.set(f'{course} · 暂无视频资源')

    def _render_draft(self):
        building = self._catalog_building
        self._catalog_building = True
        self.course_panel.set_enabled(True)
        course_rows = [{'key': group['key'], 'label': group['course']['label'],
                        'detail': f"{len(group['videos'])} 个视频 · " + group['course'].get('detail', '')}
                       for group in self.draft.groups]
        self.course_panel.set_items(course_rows, multiple=False, selected_keys=[self.draft.current])
        self._load_draft_course()
        self._catalog_building = building

    def _update_step(self):
        phase = self._last_phase
        stage = (4 if phase in ('loading_video', 'playing', 'complete') or self.selection_stage == 'playing' else
                 3 if phase == 'choosing_video' or self.selection_stage == 'videos'
                 else 2 if phase in ('choosing_course', 'loading_resources') or self.selection_stage == 'courses'
                 or self.selection_stage == 'scanning' else 1)
        names = ['连接', '选课扫描', '视频清单', '播放']
        self.step_var.set('    →    '.join(f'{"●" if i == stage else "✓" if i < stage else "○"} {name}'
                                         for i, name in enumerate(names, 1)))

    def _show_selection(self, data, *, query=None, selected_key=None, selected_keys=None):
        self._capture_catalog()
        self.request_id, self._selection_data = data["request_id"], data
        self.selection_stage = 'courses' if data['title'] == '课程' else 'videos'
        self.active_panel = self.course_panel if data["title"] == "课程" else self.video_panel
        self._catalog_building = True
        self.active_panel.set_enabled(True)
        explicit = selected_keys if selected_keys is not None else [selected_key] if selected_key else None
        # A fresh course request never guesses whether a previously selected
        # course has since been completed. Zoom restores the same request by
        # passing its selected keys explicitly.
        if self.selection_stage == 'courses' and explicit is None and data.get('multiple', False):
            explicit = []
        if self.selection_stage == 'courses' and any(
                row['key'].startswith('scan:') for row in self.course_panel.rows):
            # The plan's course list is navigation, not the user's original
            # course selection. Restore that selection before matching a rescan.
            self.course_panel.multiple = True
            self.course_panel.listbox.configure(selectmode='multiple')
            self.course_panel.load(self.course_cache)
        if self.selection_stage == 'videos' and self._plan_ready:
            self._render_draft()
        else:
            self.active_panel.set_items(data["choices"], multiple=data.get("multiple", False),
                                        selected_keys=explicit)
        if query is not None:
            self.active_panel.query_var.set(query)
        self._catalog_building = False
        # Compatibility alias: this is a frame inside the main window, never a Toplevel.
        self.dialog = self.catalog_page
        self._selection_aliases()
        self._catalog_changed()
        self._update_step()
        self._show("catalog")
        if self.state() == 'iconic':
            self.deiconify()
        self.lift()
        self.active_panel.search.focus_set()

    def _color_dialog(self):
        self.course_panel.apply_theme()
        self.video_panel.apply_theme()

    def _filter_choices(self, *_):
        if self.active_panel:
            self.active_panel.filter()

    def _sync_selection(self):
        if self.active_panel:
            self.active_panel.sync()
            self._selection_aliases()

    def _selection_changed(self, event=None):
        if self.active_panel:
            self.active_panel.changed()

    def _select_visible(self):
        self.active_panel.select_visible()

    def _clear_selection(self):
        self.active_panel.clear()

    def _selected_keys(self):
        if self.selection_stage == 'videos' and self._plan_ready:
            self.draft.update_current(self.video_panel.selected())
            return self.draft.ordered_keys()
        return self.active_panel.selected() if self.active_panel else []

    def _selected_key(self):
        if self.active_panel is None:
            return None
        selected = self.active_panel.listbox.curselection()
        return self.active_panel.visible_rows[selected[0]]["key"] if selected else None

    def _confirm_selection(self):
        if self.request_id is None:
            return
        keys = self._selected_keys()
        if keys:
            selecting_courses = self._selection_data['title'] == '课程'
            self.controller.resolve(self.request_id,
                                    keys if self._selection_data.get("multiple") else keys[0])
            self._dismiss_dialog()
            self.selection_stage = 'scanning' if selecting_courses else 'playing'
            self.message_var.set('正在扫描所选课程的视频；完成后将显示播放清单。'
                                 if selecting_courses else '已确认播放清单，正在启动队列。')
            self._catalog_changed()
            self._show("monitor")

    def _confirm_from_panel(self, event):
        if self.active_panel and event.widget is self.active_panel.listbox:
            self._confirm_selection()

    def _cancel_selection(self):
        if self.request_id:
            self.controller.resolve(self.request_id, None)
        self._dismiss_dialog()

    def _dismiss_dialog(self):
        self._capture_catalog()
        self.dialog = self.request_id = self._selection_data = None
        if not self._catalog_building:
            self._catalog_changed()

    def _stop(self):
        self.controller.stop()
        self._dismiss_dialog()
        self.status_var.set("正在停止")
        self.stop_button.configure(state="disabled")

    def _close(self):
        if self.controller.running:
            self.closing = True
            self._stop()
        else:
            self._dismiss_dialog()
            self.destroy()

    def _append_log(self, message):
        self._pending_logs.append(f"[{datetime.now():%H:%M:%S}] {message}\n")
        if self._log_job is None:
            self._log_job = self.after(30, self._flush_logs)

    def _flush_logs(self):
        if self._log_job:
            self.after_cancel(self._log_job)
            self._log_job = None
        if not self._pending_logs:
            return
        follow = self.log_view.yview()[1] >= .995
        text = "".join(self._pending_logs)
        self._pending_logs.clear()
        self.log_view.configure(state="normal")
        self.log_view.insert("end", text)
        overflow = int(self.log_view.index("end-1c").split(".")[0]) - 1201
        if overflow > 0:
            self.log_view.delete("1.0", f"{overflow + 1}.0")
        if follow:
            self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def _log_scroll_changed(self, first, last):
        self.log_scrollbar.set(first, last)
        visible = float(first) > .001 or float(last) < .999
        if visible != self._log_scroll_visible:
            self._log_scroll_visible = visible
            self.log_scrollbar.grid() if visible else self.log_scrollbar.grid_remove()

    @staticmethod
    def _format_time(value):
        seconds = int(finite_number(value))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def report_callback_exception(self, exc_type, value, tb):
        path = PROJECT_ROOT / "artifacts" / "gui_errors.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            traceback.print_exception(exc_type, value, tb, file=stream)
        self.status_var.set("界面操作失败")
        self.message_var.set(f"界面仍在运行。错误已记录到 {path}")

    def destroy(self):
        if threading.get_ident() != self._owner_thread:
            raise RuntimeError("Tk 界面必须由创建它的主线程关闭。")
        self.controller.stop()
        self._dismiss_dialog()
        for name in ("_poll_job", "_display_job", "_log_job"):
            if getattr(self, name, None):
                try:
                    self.after_cancel(getattr(self, name))
                except tk.TclError:
                    pass
                setattr(self, name, None)
        # Tk Variable holds a reference back to the root. Break that cycle while
        # this thread still owns a live Tcl interpreter, rather than letting a
        # later worker-thread garbage collection finalize it.
        variable_names = [
            name for name, value in vars(self).items()
            if isinstance(value, tk.Variable)
        ]
        for name in variable_names:
            setattr(self, name, None)
        self.theme.close()
        super().destroy()


def main():
    CourseVideoApp().mainloop()
