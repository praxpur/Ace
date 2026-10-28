"""Spacious, keyboard-operable list for course and video choices."""
import tkinter as tk
from tkinter import ttk


class ChoiceTree(ttk.Treeview):
    """Treeview with familiar click-to-toggle selection and Listbox-like helpers."""

    def __init__(self, parent, theme, is_video):
        self.theme, self.is_video = theme, is_video
        self._multiple, self._enabled = True, True
        super().__init__(parent, columns=('detail',), show='tree headings',
                         selectmode='none', height=3, style='Choice.Treeview', takefocus=True)
        self.heading('#0', text='视频' if is_video else '课程', anchor='w')
        self.heading('detail', text='状态 / 详情' if is_video else '学期 / 详情', anchor='w')
        self.column('#0', width=theme.dp(240), minwidth=theme.dp(130), stretch=True)
        self.column('detail', width=theme.dp(185), minwidth=theme.dp(110), stretch=True)
        self.bind('<Button-1>', self._click)
        self.bind('<space>', self._toggle_focused)
        self.bind('<Return>', self._toggle_focused)
        self.bind('<Up>', lambda event: self._move(-1))
        self.bind('<Down>', lambda event: self._move(1))
        self.apply_theme()

    def apply_theme(self):
        p, style, dp = self.theme.palette, self.theme.style, self.theme.dp
        style.configure('Choice.Treeview', background=p.surface_low, fieldbackground=p.surface_low,
                        foreground=p.on_surface, font=self.theme.font(13), rowheight=dp(42),
                        relief='flat', borderwidth=0, padding=0)
        style.map('Choice.Treeview', background=[('selected', p.secondary_container)],
                  foreground=[('selected', p.on_secondary_container)])
        style.configure('Choice.Treeview.Heading', background=p.surface_low, foreground=p.on_surface_variant,
                        font=self.theme.font(11, 'bold'), relief='flat', borderwidth=0, padding=(dp(8), dp(8)))
        style.map('Choice.Treeview.Heading', background=[('active', p.surface_low)])

    def configure(self, cnf=None, **options):
        if 'selectmode' in options:
            self._multiple = options.pop('selectmode') == 'multiple'
        if 'state' in options:
            self._enabled = options.pop('state') != 'disabled'
            self.state(['!disabled'] if self._enabled else ['disabled'])
        return super().configure(cnf, **options)

    config = configure

    def cget(self, key):
        if key in ('bg', 'background'):
            return self.theme.palette.surface_low
        if key == 'state':
            return 'normal' if self._enabled else 'disabled'
        return super().cget(key)

    def replace_rows(self, rows, keys, multiple):
        self._multiple = multiple
        children = self.get_children('')
        if children:
            super().delete(*children)
        for index, row in enumerate(rows):
            checked = row['key'] in keys
            super().insert('', 'end', iid=str(index), text=self._title(row, checked),
                           values=(self._detail(row),))
        selected = [str(i) for i, row in enumerate(rows) if row['key'] in keys]
        if selected:
            super().selection_set(*selected)

    def refresh_rows(self, rows, keys):
        for index, row in enumerate(rows):
            iid = str(index)
            if self.exists(iid):
                super().item(iid, text=self._title(row, row['key'] in keys),
                             values=(self._detail(row),))

    def _title(self, row, checked):
        mark = ('☑  ' if checked else '☐  ') if self._multiple else ('›  ' if checked else '   ')
        return mark + row['label']

    def _detail(self, row):
        detail = row.get('detail', '')
        if self.is_video and 'completed' in row:
            status = ('已完成' if row['completed'] is True else
                      '未完成' if row['completed'] is False else '状态未知')
            return ' · '.join(filter(None, (status, detail)))
        return detail

    def curselection(self):
        return tuple(sorted(int(item) for item in self.selection()))

    def _indices(self, first, last=None):
        count = len(self.get_children(''))
        def number(value):
            return count - 1 if value == 'end' else int(value)
        start = max(0, number(first))
        stop = min(count - 1, number(last if last is not None else first))
        return [str(index) for index in range(start, stop + 1)] if stop >= start else []

    def selection_set(self, first, last=None):
        ids = self._indices(first, last)
        if ids:
            super().selection_add(*ids)

    def selection_clear(self, first, last=None):
        ids = self._indices(first, last)
        if ids:
            super().selection_remove(*ids)

    def _click(self, event):
        if not self._enabled:
            return 'break'
        iid = self.identify_row(event.y)
        if not iid:
            return 'break'
        self.focus_set()
        self.focus(iid)
        self._toggle(iid)
        return 'break'

    def _toggle(self, iid):
        if self._multiple:
            if iid in self.selection():
                super().selection_remove(iid)
            else:
                super().selection_add(iid)
        else:
            super().selection_set(iid)
        self.event_generate('<<ChoiceChanged>>', when='tail')

    def _toggle_focused(self, event):
        if self._enabled:
            iid = self.focus() or (self.get_children('') or ('',))[0]
            if iid:
                self._toggle(iid)
        return 'break'

    def _move(self, direction):
        children = self.get_children('')
        if self._enabled and children:
            current = self.focus()
            if current in children:
                index = max(0, min(len(children) - 1, children.index(current) + direction))
            else:
                index = 0 if direction > 0 else len(children) - 1
            iid = children[index]
            self.focus(iid)
            self.see(iid)
            if not self._multiple:
                self._toggle(iid)
        return 'break'
