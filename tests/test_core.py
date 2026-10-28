import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from treehouse.adapter import normalize_text, resource_title
from treehouse.cancellation import CancellationToken
from treehouse.config import Settings, application_root
from treehouse.controller import SelectionBroker
from treehouse.diagnostics import safe_url, scrub_text
from treehouse.errors import ConfigurationError, PlaybackError, UserCancelled
from treehouse.models import Choice
from treehouse.network import load_connection_mode, network_error_message, save_connection_mode
from treehouse.player import MediaSnapshot, PlaybackTracker, finite_number


class ConfigTests(unittest.TestCase):
    def test_installed_package_does_not_write_into_site_packages(self):
        installed = str(Path("somewhere") / "site-packages" / "treehouse" / "config.py")
        with patch("treehouse.config.__file__", installed), patch.dict(
                "os.environ", {"LOCALAPPDATA": str(Path("user-data"))}):
            self.assertEqual(application_root(), Path("user-data") / "Treehouse")

    def test_invalid_url_and_port(self):
        for url in ("file:///a", "abc", "https://host:invalid", "https://user:pass@host"):
            with self.subTest(url=url), self.assertRaises(ConfigurationError):
                Settings(start_url=url).validate()

    def test_nonfinite_timeouts(self):
        for value in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                Settings(login_timeout=value).validate()

    def test_corrupt_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auth.json"
            path.write_text("not JSON", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                Settings(state_path=path).validate()

    def test_valid_session(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auth.json"
            path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
            self.assertEqual(Settings(state_path=path).validate().state_path, path)

    def test_session_not_implicitly_saved(self):
        self.assertIsNone(Settings().save_state_path)

    def test_connection_mode_validation(self):
        self.assertEqual(Settings().validate().connection_mode, 'system')
        self.assertEqual(Settings(connection_mode='direct').validate().connection_mode, 'direct')
        with self.assertRaises(ConfigurationError):
            Settings(connection_mode='invalid').validate()

    def test_connection_preference_roundtrip_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.state' / 'connection.json'
            self.assertEqual(load_connection_mode(path), 'system')
            save_connection_mode(path, 'direct')
            self.assertEqual(load_connection_mode(path), 'direct')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'mode': 'direct'})
            path.write_text('{broken', encoding='utf-8')
            self.assertEqual(load_connection_mode(path), 'system')

    def test_connection_failure_is_explained_without_exposing_url(self):
        message = network_error_message(Exception('net::ERR_TIMED_OUT at https://host/?token=secret'))
        self.assertIn('超时', message)
        self.assertIn('直接连接', message)
        self.assertNotIn('secret', message)
        self.assertIn('代理', network_error_message(Exception('net::ERR_PROXY_CONNECTION_FAILED')))
        self.assertIsNone(network_error_message(Exception('unrelated failure')))

    def test_playback_speed_is_bounded(self):
        for rate in (0, -1, True, float("nan"), float("inf"), 100):
            with self.subTest(rate=rate), self.assertRaises(ConfigurationError):
                Settings(playback_rate=rate).validate()
        self.assertEqual(Settings(playback_rate=1.5).validate().playback_rate, 1.5)


class ParsingTests(unittest.TestCase):
    def test_resource_names_with_spaces_parentheses_and_icons(self):
        self.assertEqual(
            resource_title(" 《中华人民共和国婚姻法》 (导读).mp4 （引用自课程）"),
            "《中华人民共和国婚姻法》 (导读).mp4",
        )

    def test_non_video_is_not_a_resource(self):
        self.assertIsNone(resource_title("第一章.pdf"))

    def test_font_icons_are_removed(self):
        self.assertEqual(normalize_text("  新中国史 \n "), "新中国史")

    def test_sensitive_query_and_userinfo_are_redacted(self):
        url = safe_url("https://user:password@host/p?courseId=123&token=secret&redirect=http://private#x")
        self.assertIn("courseId=123", url)
        for secret in ("password", "secret", "private", "user", "#x"):
            self.assertNotIn(secret, url)

    def test_progress_numbers_are_finite(self):
        for value in (float("nan"), float("inf"), -1, None, True):
            self.assertEqual(finite_number(value), 0)

    def test_errors_and_traceback_urls_are_redacted(self):
        text = scrub_text("goto https://host/p?token=privatevalue&courseId=1 password=privatepass")
        self.assertNotIn("privatevalue", text)
        self.assertNotIn("privatepass", text)
        self.assertIn("courseId=1", text)


def snapshot(**changes):
    data = {
        "current": 0, "duration": 5, "paused": False, "ended": False,
        "started": True, "connected": True, "loop": False, "error": None,
    }
    data.update(changes)
    return MediaSnapshot.from_dict(data)


class PlaybackTests(unittest.TestCase):
    def test_natural_end_completes(self):
        tracker = PlaybackTracker(0, 20, 5)
        self.assertFalse(tracker.observe(snapshot(), 0))
        self.assertFalse(tracker.observe(snapshot(current=2), 2))
        self.assertTrue(tracker.observe(snapshot(current=5, ended=True), 5))

    def test_ended_before_playing_does_not_pass(self):
        tracker = PlaybackTracker(0, 20, 5)
        self.assertFalse(tracker.observe(snapshot(ended=True, started=False), 0))

    def test_disconnected_video_fails(self):
        with self.assertRaises(PlaybackError):
            PlaybackTracker(0, 20, 5).observe(snapshot(connected=False), 0)

    def test_media_error_fails(self):
        with self.assertRaisesRegex(PlaybackError, "媒体无法读取"):
            PlaybackTracker(0, 20, 5).observe(snapshot(error="媒体无法读取"), 0)

    def test_loop_fails(self):
        with self.assertRaises(PlaybackError):
            PlaybackTracker(0, 20, 5).observe(snapshot(loop=True), 0)

    def test_pause_stall_fails(self):
        with self.assertRaisesRegex(PlaybackError, "暂停"):
            PlaybackTracker(0, 20, 5).observe(snapshot(paused=True), 5)

    def test_total_timeout_is_bounded(self):
        tracker = PlaybackTracker(0, 2, 100)
        tracker.observe(snapshot(), 0)
        with self.assertRaisesRegex(PlaybackError, "限定时间"):
            tracker.observe(snapshot(current=1), 2)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.events = queue.Queue()
        self.broker = SelectionBroker(self.events.put)
        self.token = CancellationToken()
        self.choices = [Choice("first", "新中国史"), Choice("second", "新中国史", "另一个学期")]
        self.result = queue.Queue()

    def start_choice(self):
        def worker():
            try:
                self.result.put(self.broker.choose("课程", self.choices, self.token))
            except Exception as error:
                self.result.put(error)
        thread = threading.Thread(target=worker)
        thread.start()
        request = self.events.get(timeout=1).data
        return thread, request["request_id"]

    def test_duplicate_response_does_not_block_ui(self):
        thread, request = self.start_choice()
        self.assertTrue(self.broker.resolve(request, "second"))
        self.assertFalse(self.broker.resolve(request, "first"))
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.result.get(timeout=1), "second")

    def test_stop_unblocks_selection(self):
        thread, request = self.start_choice()
        self.token.cancel()
        self.broker.cancel_all()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(self.result.get(timeout=1), UserCancelled)
        self.assertFalse(self.broker.resolve(request, "first"))

    def test_cancel_selection(self):
        thread, request = self.start_choice()
        self.broker.resolve(request, None)
        thread.join(1)
        self.assertIsInstance(self.result.get(timeout=1), UserCancelled)

    def test_invalid_selection_is_rejected(self):
        thread, request = self.start_choice()
        self.broker.resolve(request, "missing")
        thread.join(1)
        self.assertIsInstance(self.result.get(timeout=1), ConfigurationError)

    def test_multi_selection_is_validated_and_deduplicated(self):
        thread, request = self.start_choice()
        self.broker.resolve(request, ["second", "first", "second"])
        thread.join(1)
        self.assertEqual(self.result.get(timeout=1), ["second", "first"])

    def test_empty_multi_selection_is_rejected(self):
        thread, request = self.start_choice()
        self.broker.resolve(request, [])
        thread.join(1)
        self.assertIsInstance(self.result.get(timeout=1), ConfigurationError)
