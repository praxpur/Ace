"""Lightweight desktop surfaces and native, keyboard-friendly selectors."""
import math
import base64
import struct
import zlib
from collections import OrderedDict
import tkinter as tk
from tkinter import font as tkfont, ttk

from .appearance import DARK, LIGHT, blend
from .choice_tree import ChoiceTree


class MaterialTheme:
    def __init__(self, root, scale, mode):
        self.root, self.scale = root, scale
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        available = set(tkfont.families(root))
        self.family = next((name for name in ("Microsoft YaHei UI", "Noto Sans CJK SC",
                                             "PingFang SC", "Segoe UI") if name in available),
                           "TkDefaultFont")
        self.images = []
        self._elements = set()
        self._button_assets = OrderedDict()
        self._applied = None
        self.apply(mode)

    def dp(self, value):
        return max(1, round(value * self.scale)) if value else 0

    def font(self, size=14, weight="normal"):
        # Pixel fonts and dimensions share one scale. Tk point scaling must not
        # multiply them a second time on 150% / 200% displays.
        return self.family, -self.dp(size), weight

    def _button_image(self, fill, outline=None):
        # Keep navigation and action controls square across all surfaces.
        radius = 0
        # ttk tiles the middle of a nine-slice image. A three-pixel center
        # caused hundreds of alpha-blend operations for a single wide button.
        size = radius * 2 + self.dp(64)
        fill_pixel = bytes.fromhex(fill[1:]) + b"\xff"
        edge_pixel = bytes.fromhex((outline or fill)[1:]) + b"\xff"
        transparent = b"\0\0\0\0"
        rows = []
        for y in range(size):
            dy = max(radius - y - .5, y + .5 - (size - radius), 0)
            inset = math.ceil(radius - math.sqrt(max(0, radius ** 2 - dy ** 2)))
            length = size - 2 * inset
            edge = min(length // 2, max(1, self.dp(1))) if outline and 1 < y < size - 2 else 0
            middle = (edge_pixel * edge + fill_pixel * (length - 2 * edge) + edge_pixel * edge
                      if edge else edge_pixel * length)
            rows.append(b"\0" + transparent * inset + middle + transparent * inset)
        def chunk(kind, data):
            return (struct.pack(">I", len(data)) + kind + data
                    + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
        # One Tcl call per image, instead of a call for every raster row.
        image = tk.PhotoImage(master=self.root, data=base64.b64encode(png), format="png")
        self.images.append(image)
        return image, radius

    def _button(self, name, fill, foreground, background, border=None):
        p, s = self.palette, self.style
        key = (name, self.mode, self.scale)
        if key in self._button_assets:
            element, _ = self._button_assets[key]
            self._button_assets.move_to_end(key)
        else:
            base, radius = self._button_image(fill, border)
            hover, _ = self._button_image(blend(foreground, fill, .08), border)
            pressed, _ = self._button_image(blend(foreground, fill, .14), border)
            focus, _ = self._button_image(fill, p.primary)
            disabled, _ = self._button_image(blend(p.on_surface, background, .12))
            element = f"{name}.{len(self._elements)}.background"
            s.element_create(element, "image", base, ("disabled", disabled),
                             ("pressed", pressed), ("focus", focus), ("active", hover),
                             border=radius, width=radius * 2 + 3, height=radius * 2 + 3,
                             sticky="nsew")
            self._elements.add(element)
            self._button_assets[key] = element, (base, hover, pressed, focus, disabled)
        s.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [
                ("Button.label", {"sticky": "nsew"})]})]})])
        s.configure(name, foreground=foreground, background=background,
                    font=self.font(13, "bold"), padding=(self.dp(16), self.dp(9)),
                    anchor="center", borderwidth=0)
        s.map(name, foreground=[("disabled", blend(p.on_surface, background, .38))])

    def apply(self, mode):
        if self._applied == (mode, self.scale):
            return
        self.mode, self.palette = mode, DARK if mode == "dark" else LIGHT
        p, s, dp = self.palette, self.style, self.dp
        self.root.configure(bg=p.surface)
        self.root.option_add("*Font", self.font())
        self.root.option_add("*TCombobox*Listbox.background", p.surface_high)
        self.root.option_add("*TCombobox*Listbox.foreground", p.on_surface)
        self.root.option_add("*TCombobox*Listbox.selectBackground", p.secondary_container)
        self.root.option_add("*TCombobox*Listbox.selectForeground", p.on_secondary_container)
        for role in ("surface", "surface_low", "surface_container", "surface_high",
                     "primary_container", "secondary_container", "sidebar"):
            bg = getattr(p, role)
            fg = (p.on_sidebar if role == 'sidebar' else
                  p.on_primary_container if role == "primary_container" else p.on_surface)
            muted = p.on_sidebar_muted if role == 'sidebar' else p.on_surface_variant
            s.configure(f"{role}.TFrame", background=bg)
            for kind, size, weight, color in (
                ("Body", 14, "normal", fg), ("Muted", 12, "normal", muted),
                ("Title", 17, "bold", fg), ("Headline", 25, "bold", fg),
                ("Caption", 11, "normal", muted),
            ):
                s.configure(f"{role}.{kind}.TLabel", background=bg, foreground=color,
                            font=self.font(size, weight))
        s.configure("TFrame", background=p.surface)
        s.configure("TLabel", background=p.surface, foreground=p.on_surface, font=self.font())
        s.configure("TEntry", fieldbackground=p.surface_high, foreground=p.on_surface,
                    insertcolor=p.primary, bordercolor=p.outline_variant, lightcolor=p.surface_high,
                    darkcolor=p.surface_high, padding=(dp(12), dp(10)), borderwidth=dp(1),
                    selectbackground=p.primary_container, selectforeground=p.on_primary_container)
        s.map("TEntry", bordercolor=[("focus", p.primary)],
              fieldbackground=[("disabled", p.surface_container)])
        s.configure("TCombobox", fieldbackground=p.surface_high, background=p.surface_high,
                    foreground=p.on_surface, arrowcolor=p.on_surface_variant,
                    bordercolor=p.outline_variant, padding=(dp(8), dp(6)), arrowsize=dp(14))
        s.map("TCombobox", fieldbackground=[("readonly", p.surface_high)],
              foreground=[("readonly", p.on_surface)], selectbackground=[("readonly", p.surface_high)],
              selectforeground=[("readonly", p.on_surface)], bordercolor=[("focus", p.primary)])
        s.configure("TCheckbutton", background=p.surface_low, foreground=p.on_surface,
                    font=self.font(), padding=dp(4), indicatorsize=dp(20),
                    indicatorbackground=p.surface_high, indicatorforeground=p.on_primary,
                    bordercolor=p.outline)
        s.map("TCheckbutton", background=[("active", p.surface_low)],
              indicatorbackground=[("selected", p.primary), ("active", p.secondary_container)])
        s.configure("Horizontal.TProgressbar", troughcolor=p.secondary_container,
                    background=p.primary, borderwidth=0, lightcolor=p.primary, darkcolor=p.primary,
                    thickness=dp(8))
        s.configure("TScrollbar", background=p.surface_high, troughcolor=p.surface_low,
                    arrowcolor=p.on_surface_variant, borderwidth=0, arrowsize=dp(12), width=dp(12))
        s.map("TScrollbar", background=[("active", p.outline_variant)])
        self._button("Filled.TButton", p.primary, p.on_primary, p.surface)
        self._button("Tonal.TButton", p.secondary_container, p.on_secondary_container, p.surface_low)
        self._button("Text.TButton", p.surface_low, p.primary, p.surface_low)
        self._button("Nav.TButton", p.sidebar, p.on_sidebar_muted, p.sidebar)
        self._button("Selected.Nav.TButton", p.sidebar_selected, p.on_sidebar_selected, p.sidebar)
        self._button("Theme.TButton", p.sidebar, p.on_sidebar_muted, p.sidebar)
        self._button("Selected.Theme.TButton", p.sidebar_selected, p.on_sidebar_selected, p.sidebar)
        for name in ('Nav.TButton', 'Selected.Nav.TButton'):
            s.configure(name, anchor='w', padding=(dp(14), dp(10)), font=self.font(13, 'bold'))
        for name in ("Theme.TButton", "Selected.Theme.TButton"):
            s.configure(name, padding=(dp(9), dp(8)), font=self.font(12))
        s.configure("Small.Text.TButton", padding=(dp(8), dp(6)), font=self.font(12))
        # ttk fills the widget rectangle before drawing the transparent rounded
        # image. Every state must use the actual parent's surface color.
        for role in ("surface", "surface_low", "surface_container", "surface_high",
                     "primary_container", "secondary_container", "sidebar"):
            bg = getattr(p, role)
            for kind in ("Filled", "Tonal", "Text", "Small.Text", "Nav", "Selected.Nav",
                         "Theme", "Selected.Theme"):
                name = f"{role}.{kind}.TButton"
                s.configure(name, background=bg, relief="flat", borderwidth=0,
                            bordercolor=bg, lightcolor=bg, darkcolor=bg, focuscolor=bg)
                s.map(name, background=[("disabled", bg), ("pressed", bg),
                                        ("active", bg), ("focus", bg)])
        while len(self._button_assets) > 56:
            self._button_assets.popitem(last=False)
        self.images[:] = [image for _, images in self._button_assets.values() for image in images]
        self._applied = mode, self.scale

    def close(self):
        self._button_assets.clear()
        self.images.clear()


class MaterialButton(ttk.Button):
    """Scope a rounded button's surrounding background to its parent surface."""
    def __init__(self, parent, theme, **options):
        try:
            role = str(parent.cget("style")).split(".")[0]
        except tk.TclError:
            role = "surface"
        self.surface_role = role if hasattr(theme.palette, role) else "surface"
        options["style"] = self._scoped(options.get("style", "Tonal.TButton"))
        super().__init__(parent, **options)

    def _scoped(self, style):
        return style if style.startswith(self.surface_role + ".") else f"{self.surface_role}.{style}"

    def configure(self, cnf=None, **options):
        if "style" in options:
            options["style"] = self._scoped(options["style"])
        return super().configure(cnf, **options)


class ChoicePanel(ttk.Frame):
    """An inline, reusable selector whose rows and checked identities survive failures."""
    def __init__(self, parent, theme, title, query_var, count_var, on_change):
        super().__init__(parent, style="surface_low.TFrame")
        self.theme, self.query_var, self.count_var = theme, query_var, count_var
        self.on_change = on_change
        self.rows, self.visible_rows, self.keys = [], [], set()
        self.multiple = True
        self.is_video = title == '视频'
        dp = theme.dp
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(2, weight=1)
        self.title_label = ttk.Label(self, text=title, style="surface_low.Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, dp(10)))
        ttk.Label(self, textvariable=count_var, style="surface_low.Caption.TLabel").grid(
            row=0, column=1, sticky="e", pady=(0, dp(10)))
        search_row = ttk.Frame(self, style='surface_low.TFrame')
        search_row.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, dp(12)))
        search_row.columnconfigure(1, weight=1)
        ttk.Label(search_row, text='搜索', style='surface_low.Muted.TLabel').grid(
            row=0, column=0, sticky='w', padx=(0, dp(10)))
        self.search = ttk.Entry(search_row, textvariable=query_var, font=theme.font(13), width=1)
        self.search.grid(row=0, column=1, sticky='ew')
        results = ttk.Frame(self, style="surface_low.TFrame")
        results.grid(row=2, column=0, columnspan=2, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.listbox = ChoiceTree(results, theme, self.is_video)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.vertical = ttk.Scrollbar(results, command=self.listbox.yview)
        self.horizontal = ttk.Scrollbar(results, orient="horizontal", command=self.listbox.xview)
        self._scroll_visible = {"vertical": True, "horizontal": True}
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.listbox.configure(yscrollcommand=lambda a, b: self._scroll("vertical", a, b),
                               xscrollcommand=lambda a, b: self._scroll("horizontal", a, b))
        tools = ttk.Frame(self, style="surface_low.TFrame")
        self.tools = tools
        tools.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(dp(10), 0))
        tools.columnconfigure((0, 1, 2) if self.is_video else (0, 1), weight=1, uniform="tools")
        self.all_button = MaterialButton(tools, theme, text="全选", style="Small.Text.TButton",
                                          command=self.select_visible)
        self.clear_button = MaterialButton(tools, theme, text="清空", style="Small.Text.TButton",
                                            command=self.clear)
        self.all_button.grid(row=0, column=0, sticky="ew", padx=(0, dp(4)))
        self.unfinished_button = None
        if self.is_video:
            self.unfinished_button = MaterialButton(tools, theme, text='选未完成',
                                                     style='Small.Text.TButton',
                                                     command=self.select_unfinished)
            self.unfinished_button.grid(row=0, column=1, sticky='ew', padx=dp(4))
        self.clear_button.grid(row=0, column=2 if self.is_video else 1, sticky="ew", padx=(dp(4), 0))
        self.listbox.bind("<<ChoiceChanged>>", lambda event: self.changed())
        self._trace = query_var.trace_add("write", lambda *_: self.filter())
        self.apply_theme()
        self._render()

    def _scroll(self, axis, first, last):
        bar = getattr(self, axis)
        bar.set(first, last)
        visible = float(first) > .001 or float(last) < .999
        if visible != self._scroll_visible[axis]:
            self._scroll_visible[axis] = visible
            bar.grid() if visible else bar.grid_remove()

    @staticmethod
    def identity(row):
        return row["label"], row.get("detail", "")

    def sync(self):
        self.keys.difference_update(row["key"] for row in self.visible_rows)
        self.keys.update(self.visible_rows[index]["key"] for index in self.listbox.curselection()
                         if index < len(self.visible_rows))

    def export(self):
        self.sync()
        return {"choices": list(self.rows), "selected": [row["key"] for row in self.rows
                                                         if row["key"] in self.keys]}

    def load(self, state):
        self.rows = list(state.get("choices", []))
        self.keys = set(state.get("selected", []))
        self.visible_rows = []
        self._render()

    def set_items(self, rows, multiple=True, selected_keys=None):
        self.sync()
        identities = {self.identity(row) for row in self.rows if row["key"] in self.keys}
        had_rows = bool(self.rows)
        self.rows, self.multiple = list(rows), multiple
        self.listbox.configure(selectmode="multiple" if multiple else "browse")
        self.keys = (set(selected_keys) if selected_keys is not None else {
            row["key"] for row in self.rows if self.identity(row) in identities})
        if not had_rows and selected_keys is None and self.rows and not multiple:
            self.keys.add(self.rows[0]["key"])
        self.visible_rows = []
        self._render()

    def filter(self):
        self.sync()
        self._render()

    def _render(self):
        query = self.query_var.get().strip().casefold()
        self.visible_rows = [row for row in self.rows if query in (
            row["label"] + " " + row.get("detail", "")).casefold()]
        if not self.multiple and not any(row["key"] in self.keys for row in self.visible_rows):
            self.keys = {self.visible_rows[0]["key"]} if self.visible_rows else set()
        self.listbox.replace_rows(self.visible_rows, self.keys, self.multiple)
        self.changed()

    def changed(self):
        self.sync()
        self.listbox.refresh_rows(self.visible_rows, self.keys)
        if not self.multiple:
            self.count_var.set(f'{len(self.rows)} 门课程')
        elif self.is_video:
            self.count_var.set(f'本课已选 {len(self.keys)} / {len(self.rows)}')
        else:
            self.count_var.set(f'已选 {len(self.keys)} / {len(self.rows)} 门')
        self.on_change()

    def set_enabled(self, enabled):
        state = 'normal' if enabled else 'disabled'
        self.listbox.configure(state=state)
        self.search.configure(state=state)
        self.all_button.configure(state=state)
        self.clear_button.configure(state=state)
        if self.unfinished_button:
            self.unfinished_button.configure(state=state)

    def selected(self):
        self.sync()
        return [row["key"] for row in self.rows if row["key"] in self.keys]

    def select_visible(self):
        self.listbox.selection_set(0, "end")
        self.changed()

    def select_unfinished(self):
        for index, row in enumerate(self.visible_rows):
            if row.get('completed') is False:
                self.listbox.selection_set(index)
        self.changed()

    def clear(self):
        self.keys.clear()
        self.listbox.selection_clear(0, "end")
        self.changed()

    def apply_theme(self):
        self.listbox.apply_theme()

    def destroy(self):
        self.query_var.trace_remove("write", self._trace)
        self.query_var = self.count_var = None
        super().destroy()


class Surface(tk.Frame):
    """Square-corner panel separated from its content layout."""
    def __init__(self, parent, theme, role="surface_low", padding=24, backdrop="surface"):
        super().__init__(parent, borderwidth=0, highlightthickness=0)
        self.theme, self.role, self.backdrop = theme, role, backdrop
        self._draw_key = None
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, takefocus=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = ttk.Frame(self, style=f"{role}.TFrame")
        self.body.pack(fill="both", expand=True, padx=theme.dp(padding), pady=theme.dp(padding))
        self.canvas.bind("<Configure>", self._draw)
        self.apply_theme()

    def _draw(self, event=None):
        key = (self.canvas.winfo_width(), self.canvas.winfo_height(),
               getattr(self.theme.palette, self.role))
        if key == self._draw_key:
            return
        self._draw_key = key
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, key[0], key[1], fill=key[2], outline='')

    def apply_theme(self):
        bg = getattr(self.theme.palette, self.backdrop)
        self.configure(bg=bg)
        self.canvas.configure(bg=bg)
        self._draw()


class ScrollPage(ttk.Frame):
    """A width-following settings page, scrollable on smaller high-DPI screens."""
    def __init__(self, parent, theme, fill_height=False):
        super().__init__(parent)
        self.theme = theme
        self.fill_height = fill_height
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, takefocus=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self._scroll_visible = True
        self.canvas.configure(yscrollcommand=self._set_scroll, yscrollincrement=theme.dp(24))
        self.body = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", self._size)
        self._size_key = self._region = None
        self.body.bind("<Configure>", self._body_size)
        self.apply_theme()

    def _size(self, event):
        key = (max(1, event.width), event.height)
        if self._size_key == key:
            return
        self._size_key = key
        self.canvas.itemconfigure(self.window, width=key[0])
        if self.fill_height:
            self.canvas.itemconfigure(self.window, height=max(event.height, self.body.winfo_reqheight()))

    def _body_size(self, event):
        region = self.canvas.bbox("all")
        if region != self._region:
            self._region = region
            self.canvas.configure(scrollregion=region)

    def _set_scroll(self, first, last):
        self.scrollbar.set(first, last)
        visible = float(first) > .001 or float(last) < .999
        if visible != self._scroll_visible:
            self._scroll_visible = visible
            if visible:
                self.scrollbar.grid()
            else:
                self.scrollbar.grid_remove()

    def scroll(self, event):
        if self.body.winfo_height() <= self.canvas.winfo_height():
            return
        if getattr(event, "num", None) in (4, 5):
            amount = -1 if event.num == 4 else 1
        else:
            amount = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(amount * 2, "units")

    def ensure_visible(self, widget):
        self.update_idletasks()
        total = self.body.winfo_height()
        top = widget.winfo_rooty() - self.body.winfo_rooty()
        visible_top = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        if top < visible_top:
            self.canvas.yview_moveto(max(0, top - self.theme.dp(12)) / max(1, total))
        elif top + widget.winfo_height() > visible_top + height:
            self.canvas.yview_moveto((top + widget.winfo_height() - height
                                     + self.theme.dp(12)) / max(1, total))

    def apply_theme(self):
        self.canvas.configure(bg=self.theme.palette.surface)
