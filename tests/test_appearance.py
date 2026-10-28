import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from treehouse.appearance import Appearance, DARK, LIGHT, effective_scale, resolve_theme
from treehouse.display import fit_window


def contrast(a, b):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                  for value in channels]
        return sum(channel * weight for channel, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)


class AppearanceTests(unittest.TestCase):
    def test_dpi_and_zoom_multiply_exactly_once(self):
        for dpi, expected in ((96, 1), (120, 1.25), (144, 1.5), (192, 2)):
            self.assertEqual(effective_scale(dpi), expected)
            self.assertEqual(effective_scale(dpi, 1.5), expected * 1.5)

    def test_invalid_dpi_is_bounded(self):
        for value in (0, -100, float("nan"), float("inf")):
            self.assertEqual(effective_scale(value), 1)
        self.assertEqual(effective_scale(9600), 6)

    def test_text_color_pairs_have_aa_contrast(self):
        for palette in (LIGHT, DARK):
            for foreground, background in ((palette.on_surface, palette.surface_low),
                                           (palette.on_surface_variant, palette.surface_low),
                                           (palette.on_primary, palette.primary),
                                           (palette.on_primary_container, palette.primary_container),
                                           (palette.on_secondary_container, palette.secondary_container),
                                           (palette.on_sidebar, palette.sidebar),
                                           (palette.on_sidebar_muted, palette.sidebar),
                                           (palette.on_sidebar_selected, palette.sidebar_selected),
                                           (palette.error, palette.surface),
                                           (palette.success, palette.surface)):
                with self.subTest(fg=foreground, bg=background):
                    self.assertGreaterEqual(contrast(foreground, background), 4.5)

    def test_preferences_store_only_appearance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ui" / "appearance.json"
            Appearance("dark", 1.3).save(path)
            self.assertEqual(Appearance.load(path), Appearance("dark", 1.3))
            self.assertEqual(set(json.loads(path.read_text())), {"theme", "zoom"})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_corrupt_and_invalid_preferences_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "appearance.json"
            for content in ("invalid", "[]", "null", '{"theme":"invalid","zoom":true}',
                            '{"theme":{},"zoom":90}'):
                path.write_text(content)
                self.assertEqual(Appearance.load(path), Appearance())

    def test_system_theme_and_explicit_override(self):
        with patch("treehouse.appearance.system_is_dark", return_value=True):
            self.assertEqual(resolve_theme("system"), "dark")
            self.assertEqual(resolve_theme("light"), "light")

    def test_geometry_fits_small_and_negative_origin_monitor(self):
        width, height, x, y = fit_window(2320, 1720, (-1920, 0, 1920, 1040))
        self.assertGreaterEqual(x, -1920)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + width, 0)
        self.assertLessEqual(y + height, 1040)
