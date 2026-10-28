"""Small code-drawn elements used by the desktop shell."""
import tkinter as tk


class BrandMark(tk.Canvas):
    def __init__(self, parent, theme):
        self.theme = theme
        size = theme.dp(38)
        super().__init__(parent, width=size, height=size, highlightthickness=0, borderwidth=0,
                         takefocus=0)
        self.apply_theme()

    def apply_theme(self):
        p, dp = self.theme.palette, self.theme.dp
        self.configure(bg=p.sidebar)
        self.delete('all')
        size = dp(38)
        self.create_rectangle(dp(1), dp(1), size - dp(1), size - dp(1),
                              fill=p.sidebar_selected, outline='')
        self.create_line(dp(19), dp(29), dp(19), dp(12), fill=p.on_sidebar,
                         width=dp(2), capstyle='round')
        self.create_line(dp(19), dp(21), dp(11), dp(16), fill=p.on_sidebar,
                         width=dp(2), capstyle='round')
        self.create_line(dp(19), dp(18), dp(27), dp(12), fill=p.on_sidebar,
                         width=dp(2), capstyle='round')
        for x, y in ((10, 15), (27, 11), (19, 10)):
            self.create_rectangle(dp(x - 2), dp(y - 2), dp(x + 2), dp(y + 2),
                                  fill=p.primary, outline='')


class StepStrip(tk.Canvas):
    """A compact progress rail driven by the existing step text variable."""
    LABELS = ('连接', '选课扫描', '视频清单', '播放')

    def __init__(self, parent, theme, variable):
        self.theme, self.variable = theme, variable
        super().__init__(parent, height=theme.dp(46), highlightthickness=0, borderwidth=0,
                         takefocus=0)
        self._trace = variable.trace_add('write', lambda *_: self._draw())
        self.bind('<Configure>', self._draw)
        self.apply_theme()

    def apply_theme(self):
        self.configure(bg=self.theme.palette.surface)
        self._draw()

    def _draw(self, event=None):
        if not self.winfo_exists():
            return
        self.delete('all')
        p, dp = self.theme.palette, self.theme.dp
        width = self.winfo_width()
        if width < dp(100):
            return
        segments = self.variable.get().split('→')
        active = next((i for i, segment in enumerate(segments) if '●' in segment), 0)
        active = min(active, len(self.LABELS) - 1)
        margin = min(dp(44), max(dp(24), width // 8))
        positions = [margin + (width - 2 * margin) * i / 3 for i in range(4)]
        y = dp(10)
        for i in range(3):
            self.create_line(positions[i], y, positions[i + 1], y,
                             fill=p.primary if i < active else p.outline_variant, width=dp(2))
        for i, (x, label) in enumerate(zip(positions, self.LABELS)):
            radius = dp(5)
            self.create_rectangle(x - radius, y - radius, x + radius, y + radius,
                             fill=p.primary if i <= active else p.surface,
                             outline=p.primary if i <= active else p.outline, width=dp(1))
            if i < active:
                self.create_text(x, y, text='✓', fill=p.on_primary, font=self.theme.font(8, 'bold'))
            self.create_text(x, dp(31), text=label,
                             fill=p.on_surface if i == active else p.on_surface_variant,
                             font=self.theme.font(11, 'bold' if i == active else 'normal'))

    def destroy(self):
        self.variable.trace_remove('write', self._trace)
        self.variable = None
        super().destroy()
