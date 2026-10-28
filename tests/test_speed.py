import unittest

from treehouse.speed import allowed_rate, parse_rate


class SpeedTests(unittest.TestCase):
    def test_menu_label_and_selected_accessibility_text(self):
        self.assertEqual(parse_rate("1.5x, selected"), 1.5)
        self.assertEqual(parse_rate("2倍"), 2)
        self.assertIsNone(parse_rate("Playback Rate"))
        self.assertIsNone(parse_rate("16.5x"))

    def test_unavailable_speed_uses_supported_lower_option(self):
        self.assertEqual(allowed_rate(2, [1, 1.5, 3]), 1.5)
        self.assertIsNone(allowed_rate(1, [1.5, 2]))
