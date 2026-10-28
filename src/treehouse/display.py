"""Process-local DPI support. No global display settings are changed."""
import ctypes
import os


def enable_dpi_awareness():
    """Call before the first Tk window; an existing host DPI policy is respected."""
    if os.name != "nt":
        return
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        setter = user32.SetProcessDpiAwarenessContext
        setter.argtypes, setter.restype = [ctypes.c_void_p], ctypes.c_bool
        if setter(ctypes.c_void_p(-4)) or ctypes.get_last_error() == 5:
            return  # PER_MONITOR_AWARE_V2, or awareness was already set by the host.
    except (AttributeError, OSError):
        pass
    try:
        setter = ctypes.windll.shcore.SetProcessDpiAwareness
        setter.argtypes, setter.restype = [ctypes.c_int], ctypes.c_long
        if setter(2) in (0, -2147024891):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def window_dpi(window) -> float:
    if os.name == "nt":
        try:
            api = ctypes.windll.user32.GetDpiForWindow
            api.argtypes, api.restype = [ctypes.c_void_p], ctypes.c_uint
            dpi = api(window.winfo_id())
            if dpi:
                return float(dpi)
        except (AttributeError, OSError):
            pass
    return float(window.winfo_fpixels("1i"))


def work_area(window):
    """Physical-pixel monitor work area, excluding the Windows taskbar."""
    if os.name == "nt":
        try:
            from ctypes import wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                            ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

            user32 = ctypes.windll.user32
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            info = MonitorInfo()
            info.size = ctypes.sizeof(info)
            monitor = user32.MonitorFromWindow(window.winfo_id(), 2)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                rect = info.work
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except (AttributeError, OSError):
            pass
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


def fit_window(width, height, area, margin=24):
    """Keep both the initial window and dialogs inside the available work area."""
    left, top, available_width, available_height = area
    width = min(max(1, round(width)), max(1, available_width - margin * 2))
    height = min(max(1, round(height)), max(1, available_height - margin * 2))
    return width, height, left + (available_width - width) // 2, top + (available_height - height) // 2


def colorref(color):
    red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
    return red | (green << 8) | (blue << 16)


def theme_window_frame(window, palette, dark):
    """Theme the real Windows caption, including its native window controls."""
    if os.name != "nt":
        return {}
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = user32.GetAncestor(window.winfo_id(), 2) or window.winfo_id()
        setter = ctypes.windll.dwmapi.DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        values = {20: int(dark), 33: 2, 34: colorref(palette.outline_variant),
                  35: colorref(palette.surface), 36: colorref(palette.on_surface)}
        results = {}
        for attribute, raw in values.items():
            value = wintypes.DWORD(raw)
            results[attribute] = setter(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0
        return results  # Unsupported attributes on older Windows fail harmlessly.
    except (AttributeError, OSError):
        return {}
