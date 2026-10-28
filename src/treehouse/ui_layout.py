"""Desktop view construction and appearance updates, separate from task events."""
import tkinter as tk
from dataclasses import replace
from tkinter import ttk

from .appearance import resolve_theme
from .config import PLAYBACK_RATES
from .display import fit_window, theme_window_frame, window_dpi, work_area
from .desktop_chrome import BrandMark, StepStrip
from .network import CONNECTION_LABELS
from .ui_widgets import ChoicePanel, MaterialButton, ScrollPage, Surface

THEME_LABELS = {"system": "自动", "light": "浅色", "dark": "深色"}
ZOOM_LABELS = {"85%": .85, "100%": 1.0, "115%": 1.15, "130%": 1.3, "150%": 1.5}


class MaterialView:
    """Only the owning Tk thread calls these view methods."""
    def _label(self, parent, text=None, variable=None, role="surface_low", kind="Body", **kw):
        return ttk.Label(parent, text=text, textvariable=variable,
                         style=f"{role}.{kind}.TLabel", **kw)

    def _button(self, parent, **options):
        return MaterialButton(parent, self.theme, **options)

    def _wrap(self, label, parent, inset=0):
        last_width = None
        def resized(event):
            nonlocal last_width
            width = max(self.theme.dp(80), event.width - self.theme.dp(inset))
            if width != last_width:
                last_width = width
                label.configure(wraplength=width)
        parent.bind("<Configure>", resized, add="+")

    def _build(self):
        dp = self.theme.dp
        self._layout_signature = None
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.shell = ttk.Frame(self)
        self.shell.grid(row=0, column=0, sticky="nsew")
        self.shell.rowconfigure(0, weight=1)
        self.shell.columnconfigure(1, weight=1)
        self.sidebar = ttk.Frame(self.shell, style="sidebar.TFrame", padding=dp(18))
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(5, weight=1)
        brand_area = ttk.Frame(self.sidebar, style='sidebar.TFrame')
        brand_area.grid(row=0, column=0, sticky='ew', pady=(dp(8), dp(22)))
        self.brand_mark = BrandMark(brand_area, self.theme)
        self.brand_mark.grid(row=0, column=0, rowspan=2, sticky='w', padx=(0, dp(10)))
        self.brand = self._label(brand_area, '树屋', role='sidebar', kind='Title')
        self.brand.grid(row=0, column=1, sticky='w')
        self.brand_subtitle = self._label(brand_area, 'TREEHOUSE', role='sidebar', kind='Caption')
        self.brand_subtitle.grid(row=1, column=1, sticky='w')
        self._label(self.sidebar, '学习空间', role='sidebar', kind='Caption').grid(
            row=1, column=0, sticky='w', padx=dp(12), pady=(0, dp(8)))
        self.nav_buttons = {}
        for row, (key, title) in enumerate((("settings", "01   连接与设置"), ("catalog", "02   学习清单"),
                                            ("monitor", "03   播放监控")), 2):
            button = self._button(self.sidebar, text=title, width=15, style="Nav.TButton",
                                command=lambda view=key: self._show(view))
            button.grid(row=row, column=0, sticky="ew", pady=dp(4))
            self.nav_buttons[key] = button
        self.appearance_panel = ttk.Frame(self.sidebar, style="sidebar.TFrame")
        self.appearance_panel.grid(row=6, column=0, sticky="ew", pady=dp(12))
        self.appearance_title = self._label(self.appearance_panel, "外观", role="sidebar",
                                            kind="Muted")
        self.appearance_title.pack(anchor="w", pady=(0, dp(10)))
        themes = ttk.Frame(self.appearance_panel, style="sidebar.TFrame")
        themes.pack(fill="x")
        self.theme_buttons = {}
        for key, label in THEME_LABELS.items():
            themes.columnconfigure(len(self.theme_buttons), weight=1)
            button = self._button(themes, text=label, width=3, style="Theme.TButton",
                                command=lambda mode=key: self.set_theme(mode))
            button.grid(row=0, column=len(self.theme_buttons), sticky="ew", padx=dp(1))
            self.theme_buttons[key] = button
        self.zoom_label = self._label(self.appearance_panel, "界面缩放 · 叠加系统比例",
                                       role="sidebar", kind="Caption")
        self.zoom_label.pack(anchor="w", pady=(dp(18), dp(8)))
        self.zoom_combo = ttk.Combobox(self.appearance_panel, textvariable=self.zoom_var,
                                       values=tuple(ZOOM_LABELS), state="readonly", width=8,
                                       font=self.theme.font(13))
        self.zoom_combo.pack(fill="x")
        self.zoom_combo.bind("<<ComboboxSelected>>", lambda event: self.set_zoom(
            ZOOM_LABELS[self.zoom_var.get()]))
        self.dpi_label = self._label(self.appearance_panel, variable=self.scale_var,
                                      role="sidebar", kind="Caption")
        self.dpi_label.pack(anchor="w", pady=(dp(10), 0))

        self.main_panel = ttk.Frame(self.shell, padding=(dp(28), dp(24), dp(28), dp(16)))
        self.main_panel.grid(row=0, column=1, sticky="nsew")
        self.main_panel.columnconfigure(0, weight=1)
        self.main_panel.rowconfigure(1, weight=1)
        header = ttk.Frame(self.main_panel)
        header.grid(row=0, column=0, sticky="ew", pady=(0, dp(12)))
        header.columnconfigure(0, weight=1)
        self._label(header, "TREEHOUSE  /  学习空间", role="surface", kind="Caption").grid(
            row=0, column=0, sticky="w", pady=(0, dp(7)))
        self.page_title = self._label(header, "开始学习", role="surface", kind="Headline")
        self.page_title.grid(row=1, column=0, sticky="w")
        self.status_label = self._label(header, variable=self.status_var, role="surface", kind="Muted")
        self.status_label.grid(row=1, column=1, sticky='e', padx=(dp(12), 0))
        self.steps = StepStrip(header, self.theme, self.step_var)
        self.steps.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(dp(14), 0))
        host = ttk.Frame(self.main_panel)
        host.grid(row=1, column=0, sticky="nsew")
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)
        self.settings_page = ttk.Frame(host)
        self.catalog_page = ttk.Frame(host)
        self.monitor_page = ttk.Frame(host)
        for page in (self.settings_page, self.catalog_page, self.monitor_page):
            page.grid(row=0, column=0, sticky="nsew")
        self._build_settings()
        self._build_monitor()
        self._build_catalog()
        self._show(self.current_view)
        self._apply_widget_colors()

    def _show(self, view):
        self.current_view = view
        pages = {"settings": self.settings_page, "catalog": self.catalog_page, "monitor": self.monitor_page}
        for key, page in pages.items():
            page.grid() if key == view else page.grid_remove()
        self.page_title.configure(text={"settings": "开始学习", "catalog": "学习清单",
                                       "monitor": "播放进度"}[view])
        for key, button in self.nav_buttons.items():
            button.configure(style="Selected.Nav.TButton" if key == view else "Nav.TButton")

    def _build_settings(self):
        dp, page = self.theme.dp, self.settings_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.settings_scroll = ScrollPage(page, self.theme)
        self.settings_scroll.grid(row=0, column=0, sticky="nsew")
        content = self.settings_scroll.body
        welcome = Surface(content, self.theme, "primary_container", padding=20)
        welcome.grid(row=0, column=0, sticky="ew", pady=(0, dp(14)))
        welcome.body.columnconfigure(0, weight=1)
        self._label(welcome.body, "准备好今天的学习", role="primary_container", kind="Title").grid(
            row=0, column=0, sticky="w")
        intro = self._label(welcome.body, "连接账号后选课，扫描完成即可统一选择视频。",
                            role="primary_container", justify="left")
        intro.grid(row=1, column=0, sticky="ew", pady=(dp(7), 0))
        self._wrap(intro, welcome.body)
        card = Surface(content, self.theme, padding=20)
        card.grid(row=1, column=0, sticky="ew", pady=(0, dp(12)))
        form = card.body
        form.columnconfigure((0, 1), weight=1, uniform='settings')
        self._label(form, "连接与播放设置", kind="Title").grid(row=0, column=0, columnspan=2, sticky="w")
        help_label = self._label(form, "首次使用时，请在浏览器中手动完成登录。", kind="Muted")
        help_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(dp(5), dp(16)))
        self._wrap(help_label, form)
        self._label(form, '浏览器连接方式', kind='Muted').grid(row=2, column=0, sticky='w')
        self._label(form, '播放速度', kind='Muted').grid(row=2, column=1, sticky='w', padx=(dp(12), 0))
        self.connection_combo = ttk.Combobox(form, textvariable=self.connection_var,
                                            values=tuple(CONNECTION_LABELS.values()),
                                            state='readonly', font=self.theme.font(), width=16)
        self.connection_combo.grid(row=3, column=0, sticky='ew', pady=(dp(6), 0), padx=(0, dp(12)))
        self.speed_combo = ttk.Combobox(form, textvariable=self.speed_var,
                                       values=tuple(f"{rate:g}×" for rate in PLAYBACK_RATES),
                                       state="readonly", font=self.theme.font(), width=12)
        self.speed_combo.grid(row=3, column=1, sticky='ew', pady=(dp(6), 0), padx=(dp(12), 0))
        connection_hint = self._label(form, '代理连接失败时可选择直接连接。', kind='Caption')
        connection_hint.grid(row=4, column=0, sticky='ew', pady=(dp(6), dp(16)), padx=(0, dp(12)))
        connection_hint.configure(wraplength=dp(170))
        speed_hint = self._label(form, '以课程实际支持的速度为准。', kind='Caption')
        speed_hint.grid(row=4, column=1, sticky='ew', pady=(dp(6), dp(16)), padx=(dp(12), 0))
        speed_hint.configure(wraplength=dp(170))
        self._label(form, "课程中心地址", kind="Muted").grid(row=5, column=0, columnspan=2, sticky="w")
        self.url_entry = ttk.Entry(form, textvariable=self.url_var, font=self.theme.font(), width=16)
        self.url_entry.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(dp(6), dp(16)))
        times = ttk.Frame(form, style="surface_low.TFrame")
        times.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, dp(16)))
        times.columnconfigure((0, 1), weight=1, uniform="wait")
        for column, title, variable in ((0, "登录等待 / 秒", self.login_wait_var),
                                        (1, "播放等待上限 / 秒", self.video_wait_var)):
            field = ttk.Frame(times, style="surface_low.TFrame")
            field.grid(row=0, column=column, sticky="ew", padx=(0, dp(14)) if column == 0 else 0)
            field.columnconfigure(0, weight=1)
            self._label(field, title, kind="Muted").grid(row=0, column=0, sticky="w")
            ttk.Entry(field, textvariable=variable, font=self.theme.font(), width=8).grid(
                row=1, column=0, sticky="ew", pady=(dp(6), 0))
        self._label(form, "已有登录态文件（可选）", kind="Muted").grid(row=8, column=0, columnspan=2, sticky="w")
        state = ttk.Frame(form, style="surface_low.TFrame")
        state.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(dp(6), dp(14)))
        state.columnconfigure(0, weight=1)
        ttk.Entry(state, textvariable=self.state_var, font=self.theme.font(), width=12).grid(
            row=0, column=0, sticky="ew")
        self._button(state, text="浏览", style="Tonal.TButton", command=self._browse_state).grid(
            row=0, column=1, padx=(dp(8), 0))
        self.headless_check = ttk.Checkbutton(form, text="无头运行", variable=self.headless_var)
        state_hint = self._label(form, variable=self.state_hint_var, kind="Caption")
        state_hint.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, dp(10)))
        self._wrap(state_hint, form)
        self.headless_check.grid(row=11, column=0, sticky="w")
        hint = self._label(form, "隐藏浏览器窗口，需要有效的登录态文件。", kind="Caption")
        hint.grid(row=12, column=0, sticky="ew", padx=(dp(30), dp(8)), pady=(0, dp(12)))
        hint.configure(wraplength=dp(160))
        self.remember_check = ttk.Checkbutton(form, text="记住本次登录", variable=self.remember_var)
        self.remember_check.grid(row=11, column=1, sticky="w", padx=(dp(12), 0))
        hint = self._label(form, "登录成功后保存在本机，供下次运行使用。", kind="Caption")
        hint.grid(row=12, column=1, sticky="ew", padx=(dp(30), 0), pady=(0, dp(12)))
        hint.configure(wraplength=dp(160))
        footer = ttk.Frame(page, padding=(0, dp(16), 0, 0))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure((0, 1), weight=1, uniform='start-actions')
        self._label(footer, "连接后先选课，不会自动播放", role="surface", kind="Caption").grid(
            row=0, column=0, sticky="w", padx=(0, dp(12)))
        self.start_button = self._button(footer, text="连接并选择课程  →", style="Filled.TButton",
                                       command=self._start)
        self.start_button.grid(row=0, column=1, sticky="ew")

    def _build_monitor(self):
        dp, page = self.theme.dp, self.monitor_page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=0)
        page.rowconfigure(1, weight=1)
        progress_card = Surface(page, self.theme, padding=16)
        progress_card.grid(row=0, column=0, sticky="ew", pady=(0, dp(16)))
        body = progress_card.body
        body.columnconfigure(0, weight=1)
        heading = ttk.Frame(body, style='surface_low.TFrame')
        heading.grid(row=0, column=0, sticky='ew', pady=(0, dp(10)))
        heading.columnconfigure(0, weight=1)
        self._label(heading, '当前任务', kind='Caption').grid(row=0, column=0, sticky='w')
        self._label(heading, variable=self.queue_var, kind='Caption').grid(row=0, column=1, sticky='e')
        course = self._label(body, variable=self.course_var, kind="Title", width=1)
        course.grid(row=1, column=0, sticky="ew")
        video = self._label(body, variable=self.video_var, kind="Muted", width=1)
        video.grid(row=2, column=0, sticky="ew", pady=(dp(4), dp(10)))
        progress_header = ttk.Frame(body, style='surface_low.TFrame')
        progress_header.grid(row=3, column=0, sticky='ew')
        progress_header.columnconfigure(0, weight=1)
        self._label(progress_header, '播放进度', kind='Caption').grid(row=0, column=0, sticky='w')
        self._label(progress_header, variable=self.progress_var, kind='Muted').grid(row=0, column=1, sticky='e')
        self.progress = ttk.Progressbar(body, maximum=100)
        self.progress.grid(row=4, column=0, sticky="ew", pady=(dp(7), dp(9)))
        self.message_label = self._label(body, variable=self.message_var, kind="Muted", width=1)
        self.message_label.grid(row=5, column=0, sticky="ew")
        log_card = Surface(page, self.theme, padding=16)
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.body.columnconfigure(0, weight=1)
        log_card.body.rowconfigure(1, weight=1)
        log_heading = ttk.Frame(log_card.body, style="surface_low.TFrame")
        log_heading.grid(row=0, column=0, sticky="ew", pady=(0, dp(12)))
        log_heading.columnconfigure(0, weight=1)
        self._label(log_heading, "运行日志", kind="Title").grid(row=0, column=0, sticky="w")
        self._label(log_heading, '实时记录', kind='Caption').grid(row=0, column=1, sticky='e')
        log_host = ttk.Frame(log_card.body, style="surface_low.TFrame")
        log_host.grid(row=1, column=0, sticky="nsew")
        log_host.columnconfigure(0, weight=1)
        log_host.rowconfigure(0, weight=1)
        self.log_view = tk.Text(log_host, height=8, width=16, state="disabled", wrap="word",
                                font=self.theme.font(12), padx=dp(8), pady=dp(8),
                                relief="flat", borderwidth=0, highlightthickness=0)
        self.log_view.grid(row=0, column=0, sticky="nsew")
        self.log_scrollbar = ttk.Scrollbar(log_host, command=self.log_view.yview)
        self.log_scrollbar.grid(row=0, column=1, sticky="ns")
        self._log_scroll_visible = True
        self.log_view.configure(yscrollcommand=self._log_scroll_changed)
        footer = ttk.Frame(page, padding=(0, dp(12), 0, 0))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        diagnostic = self._label(footer, variable=self.diagnostic_var, role="surface", kind="Caption", width=1)
        diagnostic.grid(row=0, column=0, sticky="ew", padx=(0, dp(12)))
        self.stop_button = self._button(footer, text="停止任务", style="Tonal.TButton", state="disabled",
                                      command=self._stop)
        self.stop_button.grid(row=0, column=1, sticky="e")

    def _build_catalog(self):
        self._catalog_building = True
        dp, page = self.theme.dp, self.catalog_page
        page.columnconfigure(0, weight=2)
        page.columnconfigure(1, weight=3)
        page.rowconfigure(0, weight=1)
        panels, surfaces = [], []
        for column, title, query, count in (
            (0, "课程", self.course_search_var, self.course_count_var),
            (1, "视频", self.video_search_var, self.video_count_var),
        ):
            surface = Surface(page, self.theme, padding=12)
            surface.grid(row=0, column=column, sticky="nsew",
                         padx=(0, dp(6)) if column == 0 else (dp(6), 0))
            if column == 1:
                self.video_context = self._label(surface.body, variable=self.video_heading_var,
                                                 kind='Caption', width=1)
                self.video_context.pack(fill='x', pady=(0, dp(8)))
                self._wrap(self.video_context, surface.body)
            panel = ChoicePanel(surface.body, self.theme, title, query, count, self._catalog_changed)
            panel.pack(fill="both", expand=True)
            panels.append(panel)
            surfaces.append(surface)
        self.course_panel, self.video_panel = panels
        self.course_surface, self.video_surface = surfaces
        self.course_panel.load(self.course_cache)
        self.video_panel.load(self.video_caches.get(self._course_cache_key(), {}))
        footer = ttk.Frame(page, padding=(0, dp(12), 0, 0))
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure((1, 2), weight=0, uniform='catalog-actions')
        note = self._label(footer, variable=self.selection_note_var, role="surface", kind="Caption")
        note.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, dp(10)))
        self._wrap(note, footer)
        self.cancel_selection_button = self._button(footer, text="取消本次任务", style="Tonal.TButton",
                                                     command=self._cancel_selection)
        self.cancel_selection_button.grid(row=1, column=1, sticky="ew", padx=(0, dp(8)))
        self.confirm_button = self._button(footer, text="扫描所选课程的视频", style="Filled.TButton",
                                           command=self._confirm_selection)
        self.confirm_button.grid(row=1, column=2, sticky="ew")
        self.retry_button = self._button(footer, text="重新连接并选课", style="Filled.TButton",
                                         command=self._start)
        self.retry_button.grid(row=2, column=2, sticky="ew")
        self.logs_button = self._button(footer, text="查看日志", style="Tonal.TButton",
                                        command=lambda: self._show("monitor"))
        self.logs_button.grid(row=2, column=1, sticky="ew", padx=(0, dp(8)))
        self.active_panel = self.course_panel
        self._selection_aliases()
        self._catalog_building = False
        self._catalog_changed()
        # Confirmation is explicit: double-clicking a row only changes its
        # check state and never starts a scan or playback accidentally.

    def _set_catalog_layout(self):
        if not hasattr(self, 'course_surface'):
            return
        pending = self.request_id is not None
        plan = self.selection_stage == 'videos' and self._plan_ready
        courses = self.selection_stage == 'courses'
        if courses:
            self.course_surface.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=0)
            self.video_surface.grid_remove()
            self.course_panel.title_label.configure(text='选择要扫描的课程')
            self.course_panel.tools.grid()
        elif plan or (not pending and self._plan_ready):
            self.course_surface.grid(row=0, column=0, columnspan=1, sticky='nsew', padx=(0, self.theme.dp(6)))
            self.video_surface.grid(row=0, column=1, sticky='nsew', padx=(self.theme.dp(6), 0))
            self.course_panel.title_label.configure(text='已扫描课程 · 点击切换' if pending else '本次扫描课程')
            self.course_panel.tools.grid_remove()
        elif pending:
            self.course_surface.grid_remove()
            self.video_surface.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=0)
        else:
            self.course_surface.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=0)
            self.video_surface.grid_remove()
        self.course_panel.set_enabled(pending and (courses or plan))
        self.video_panel.set_enabled(pending and not courses)
        if plan:
            self.video_panel.title_label.configure(text='视频清单 · 点击勾选')

    def _apply_widget_colors(self):
        p = self.theme.palette
        def visit(widget):
            if isinstance(widget, (Surface, ScrollPage, ChoicePanel, BrandMark, StepStrip)):
                widget.apply_theme()
            for child in widget.winfo_children():
                visit(child)
        visit(self.shell)
        self.log_view.configure(bg=p.surface_low, fg=p.on_surface_variant, insertbackground=p.primary,
                                selectbackground=p.secondary_container, selectforeground=p.on_secondary_container)
        for key, button in self.theme_buttons.items():
            button.configure(style="Selected.Theme.TButton" if key == self.appearance.theme else "Theme.TButton")
        self.scale_var.set(f"系统缩放 {round(self._dpi / 96 * 100)}%")
        self._color_status()
        if self.dialog:
            self._color_dialog()
        self._theme_caption()

    def _theme_caption(self, event=None):
        if event is None or event.widget is self:
            self.caption_result = theme_window_frame(self, self.theme.palette, self.theme.mode == "dark")

    def _color_status(self):
        color = self.theme.palette.error if self._last_phase == "error" else (
            self.theme.palette.success if self._last_phase == "complete" else self.theme.palette.primary)
        self.status_label.configure(foreground=color)

    def set_theme(self, theme):
        if theme not in THEME_LABELS:
            raise ValueError("未知界面主题")
        self.appearance = replace(self.appearance, theme=theme)
        self.theme.apply(resolve_theme(theme))
        self._apply_widget_colors()
        self._save_appearance()

    def set_zoom(self, zoom):
        if zoom not in ZOOM_LABELS.values():
            raise ValueError("不支持的界面缩放比例")
        self.appearance = replace(self.appearance, zoom=zoom)
        self.zoom_var.set(f"{round(zoom * 100)}%")
        self._rescale()
        self._save_appearance()

    def _save_appearance(self):
        try:
            self.appearance.save(self.preferences_path)
        except OSError as error:
            self._append_log(f"外观已应用，但无法保存偏好：{error}")

    def _rescale(self):
        from .appearance import effective_scale
        self._flush_logs()
        log_text = self.log_view.get("1.0", "end-1c")
        progress = self.progress["value"]
        start_state, stop_state = self.start_button["state"], self.stop_button["state"]
        scroll = self.settings_scroll.canvas.yview()[0]
        selection_data = self._selection_data
        selection_stage = self.selection_stage
        self._capture_catalog()
        self._dismiss_dialog()
        self.selection_stage = 'rebuilding'
        self.shell.destroy()
        self.theme.scale = effective_scale(self._dpi, self.appearance.zoom)
        self.theme.apply(resolve_theme(self.appearance.theme))
        self._build()
        _, _, available_width, available_height = work_area(self)
        self.minsize(min(max(1, available_width - 48), self.theme.dp(600)),
                     min(max(1, available_height - 48), self.theme.dp(480)))
        self.progress.configure(value=progress)
        self.start_button.configure(state=start_state)
        self.stop_button.configure(state=stop_state)
        self.log_view.configure(state="normal")
        self.log_view.insert("1.0", log_text)
        self.log_view.configure(state="disabled")
        self.log_view.see("end")
        self.update_idletasks()
        self.settings_scroll.canvas.yview_moveto(scroll)
        self._responsive_layout()
        if selection_data:
            keys = self.course_cache.get('selected', []) if selection_data['title'] == '课程' else None
            self._show_selection(selection_data, selected_keys=keys)
        else:
            self.selection_stage = selection_stage
            self._catalog_changed()

    def _responsive_layout(self, event=None):
        if event is not None and event.widget is not self:
            return
        dp = self.theme.dp
        compact = self.winfo_width() < dp(920)
        signature = compact, self.theme.scale
        if signature == self._layout_signature:
            return
        self._layout_signature = signature
        self.compact = compact
        self.brand.configure(text="树屋")
        self.brand_subtitle.configure(text='' if compact else 'TREEHOUSE')
        self.brand_mark.grid_remove() if compact else self.brand_mark.grid()
        for key, button in self.nav_buttons.items():
            button.configure(width=4 if compact else 15,
                             text={"settings": "学习", "catalog": "选课", "monitor": "监控"}[key]
                             if compact else {"settings": "01   连接与设置", "catalog": "02   学习清单",
                                              "monitor": "03   播放监控"}[key])
        for key, button in self.theme_buttons.items():
            button.configure(text={"system": "自", "light": "浅", "dark": "深"}[key]
                             if compact else THEME_LABELS[key], width=1 if compact else 3)
        self.zoom_label.configure(text="缩放" if compact else "界面缩放 · 叠加系统比例")
        self.dpi_label.pack_forget() if compact else self.dpi_label.pack(anchor="w", pady=(dp(10), 0))
        self.sidebar.configure(padding=dp(10) if compact else dp(16))
        self.main_panel.configure(padding=(dp(16) if compact else dp(28), dp(14),
                                           dp(16) if compact else dp(28), dp(12)))

    def _display_watch(self):
        self._display_job = None
        dpi = window_dpi(self)
        if abs(dpi - self._dpi) > 1:
            self._dpi = dpi
            self._rescale()
        mode = resolve_theme(self.appearance.theme)
        if mode != self.theme.mode:
            self.theme.apply(mode)
            self._apply_widget_colors()
        self._display_job = self.after(1500, self._display_watch)

    def _scroll_settings(self, event):
        # Text handles its own wheel before the toplevel binding. Let the log
        # scroll alone instead of also moving the surrounding monitor page.
        if isinstance(event.widget, tk.Text):
            return
        if self.current_view != "settings":
            return
        page = self.settings_scroll
        widget = event.widget
        while widget is not None:
            if widget is page:
                page.scroll(event)
                return "break"
            widget = getattr(widget, "master", None)

    def _focus_settings(self, event):
        widget = event.widget
        parent = widget
        while parent is not None:
            if parent is self.settings_scroll.body:
                self.settings_scroll.ensure_visible(widget)
                break
            parent = getattr(parent, "master", None)

    def _fit_initial_window(self):
        width, height, x, y = fit_window(self.theme.dp(1160), self.theme.dp(860), work_area(self))
        self.geometry(f"{width}x{height}{x:+d}{y:+d}")
        # Small work areas remain usable with a scrolling form and fixed footer.
        self.minsize(min(width, self.theme.dp(600)), min(height, self.theme.dp(480)))
