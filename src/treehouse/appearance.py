"""Neutral desktop colors and small, non-sensitive appearance preferences."""
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Palette:
    surface: str
    surface_low: str
    surface_container: str
    surface_high: str
    on_surface: str
    on_surface_variant: str
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    secondary_container: str
    on_secondary_container: str
    outline: str
    outline_variant: str
    error: str
    error_container: str
    success: str
    sidebar: str
    on_sidebar: str
    on_sidebar_muted: str
    sidebar_selected: str
    on_sidebar_selected: str


LIGHT = Palette(
    "#F4F6F2", "#FFFFFF", "#EBF0E9", "#F0F4EF", "#1D2B24", "#52655A",
    "#19694D", "#FFFFFF", "#E2F2E7", "#154B36", "#E3EFE6", "#244E38",
    "#718579", "#D9E4DA", "#B42318", "#FDE8E5", "#146B46",
    "#172F26", "#F2F8F3", "#BBCFC0", "#305442", "#FFFFFF",
)
DARK = Palette(
    "#101A16", "#1A2921", "#18261E", "#26392D", "#E9F1E9", "#B7C9BB",
    "#9AE1B2", "#0B3623", "#214E36", "#D5F5DF", "#2B4534", "#DAEBDD",
    "#8CA998", "#405B49", "#FFB4AB", "#5E2727", "#96D9B2",
    "#101C15", "#EFF8F1", "#B6CBBB", "#2C5040", "#F5FFF8",
)
ZOOMS = (0.85, 1.0, 1.15, 1.3, 1.5)
THEMES = ("system", "light", "dark")


@dataclass(frozen=True)
class Appearance:
    theme: str = "system"
    zoom: float = 1.0

    @classmethod
    def load(cls, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            theme, zoom = data.get("theme"), data.get("zoom")
            return cls(theme if theme in THEMES else "system",
                       zoom if type(zoom) in (int, float) and zoom in ZOOMS else 1.0)
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path):
        """Replace atomically; store no URL, account, cookies or login state."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix="appearance-", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()


def effective_scale(dpi: float, zoom: float = 1.0) -> float:
    if not math.isfinite(dpi) or dpi <= 0:
        dpi = 96.0
    if not math.isfinite(zoom) or zoom <= 0:
        zoom = 1.0
    return max(0.75, min(6.0, dpi / 96 * zoom))


def system_is_dark() -> bool:
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except OSError:
            pass
    return False


def resolve_theme(theme: str) -> str:
    return "dark" if theme == "dark" or (theme == "system" and system_is_dark()) else "light"


def blend(foreground: str, background: str, opacity: float) -> str:
    values = [round(int(foreground[i:i + 2], 16) * opacity
                    + int(background[i:i + 2], 16) * (1 - opacity)) for i in (1, 3, 5)]
    return "#" + "".join(f"{value:02x}" for value in values)
