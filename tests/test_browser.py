import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from treehouse.adapter import ZhihuishuAdapter, catalog_signature
from treehouse.cancellation import CancellationToken
from treehouse.config import Settings
from treehouse.errors import LoginRequired, NavigationError, PageNotReady, UserCancelled
from treehouse.models import PageKind, Phase
from treehouse.workflow import Workflow

if os.getenv("TREE_RUN_BROWSER_TESTS") == "1":
    from tests.fixture_server import CENTER, RESOURCES, VIDEO, SHARED, FixtureServer


@unittest.skipUnless(os.getenv("TREE_RUN_BROWSER_TESTS") == "1", "use --browser")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.fixture = FixtureServer()
        cls.server = cls.fixture.__enter__()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(
            executable_path=Settings().executable(), headless=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.fixture.__exit__(None, None, None)

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.adapter = ZhihuishuAdapter(False, 0.05, self.server.profile)
        self.token = CancellationToken()
        self.phases = []

    def tearDown(self):
        self.context.close()

    def wait_ready(self, allowed, timeout=3):
        return self.adapter.wait_ready(
            self.context, allowed, timeout, self.token,
            lambda phase, message: self.phases.append(phase),
        )

    def goto(self, query):
        self.page.goto(self.server.origin + CENTER + query, wait_until="domcontentloaded")

    def test_blank_target_host_is_not_authenticated(self):
        self.goto("?case=race")
        self.assertEqual(self.adapter.probe_page(self.page)[0].kind, PageKind.LOADING)
        with self.assertRaises(LoginRequired):
            self.wait_ready({PageKind.COURSES}, 3)
        self.assertIn(Phase.WAITING_LOGIN, self.phases)

    def test_course_scan_waits_for_delayed_dom(self):
        started = time.monotonic()
        self.goto("?case=delayed")
        probe = self.wait_ready({PageKind.COURSES})
        self.assertGreater(time.monotonic() - started, 0.5)
        self.assertEqual(probe.records[0].choice.label, "新中国史")

    def test_login_in_iframe_never_passes(self):
        self.goto("?case=iframe")
        with self.assertRaises(LoginRequired):
            self.wait_ready({PageKind.COURSES}, 0.5)

    def test_popup_login_waits_for_positive_catalog(self):
        self.goto("?case=popup")
        started = time.monotonic()
        probe = self.wait_ready({PageKind.COURSES})
        self.assertGreater(time.monotonic() - started, 0.7)
        self.assertEqual(probe.kind, PageKind.COURSES)
        self.assertIn(Phase.WAITING_LOGIN, self.phases)

    def test_duplicate_course_titles_are_preserved(self):
        self.goto("?case=duplicates")
        probe = self.wait_ready({PageKind.COURSES})
        self.assertEqual(len(probe.records), 2)
        self.assertNotEqual(probe.records[0].choice.key, probe.records[1].choice.key)

    def test_explicit_empty_page_is_recognized(self):
        self.goto("?case=empty")
        self.assertEqual(self.wait_ready({PageKind.EMPTY}).kind, PageKind.EMPTY)

    def test_ai_course_dismisses_overlapping_onboarding_notices(self):
        self.page.goto(self.server.origin + CENTER)
        self.page.evaluate("""() => history.pushState({}, '',
            '/agent-course-full/test-course/stu/course-home')""")
        self.page.set_content('''<main>课程主页 我的学习</main>
            <div class="driver-popover"><button class="driver-popover-done-btn"
            onclick="this.parentElement.remove()">我知道了</button></div>
            <div id="semester"><p>平台进入新学期后，您可以切换历史学期查看教学数据</p>
            <button onclick="this.parentElement.remove()"><span>我知道了</span></button></div>''')
        probe = self.wait_ready({PageKind.COURSE_HOME})
        self.assertEqual(probe.kind, PageKind.COURSE_HOME)
        self.assertEqual(self.page.get_by_text("我知道了", exact=True).count(), 0)

    def test_unrelated_acknowledgement_is_not_dismissed(self):
        self.page.goto(self.server.origin + CENTER)
        self.page.evaluate("""() => history.pushState({}, '',
            '/agent-course-full/test-course/stu/course-home')""")
        self.page.set_content('''<main>课程主页 我的学习</main>
            <button onclick="this.remove()">我知道了</button>''')
        self.wait_ready({PageKind.COURSE_HOME})
        self.assertEqual(self.page.get_by_role("button", name="我知道了").count(), 1)

    def test_ai_resource_detail_requires_visible_iframe_video(self):
        self.page.goto(self.server.origin + CENTER)
        self.page.evaluate("""() => history.pushState({}, '',
            '/agent-course-full/course/chapter/file/resource/stu/study/resource-detail')""")
        self.page.set_content('<main>学习资源 绪论.mp4</main>')
        self.assertEqual(self.adapter.probe_page(self.page)[0].kind, PageKind.LOADING)
        self.page.set_content('''<main>学习资源 绪论.mp4</main>
            <iframe srcdoc='<video controls style="width:300px;height:200px"></video>'></iframe>''')
        probe = self.wait_ready({PageKind.VIDEO})
        self.assertEqual(probe.kind, PageKind.VIDEO)
        scope, video = self.adapter.video_locator(self.page)
        self.assertIsNot(scope, self.page.main_frame)
        self.assertTrue(video.is_visible())

    def test_shared_catalog_has_all_video_rows_and_stable_progress_identity(self):
        self.page.goto(self.server.origin + SHARED)
        probe = self.wait_ready({PageKind.RESOURCES})
        self.assertEqual([r.choice.label for r in probe.records], ['0.1 引言', '1.1 引言'])
        self.assertEqual(self.page.locator('.dialog-warn, .dialog-read, .read-learn').count(), 0)
        row = probe.records[0]
        row.locator.locator('.progress').evaluate("e => e.textContent = '99%'")
        row.locator.evaluate("e => e.classList.remove('current_play')")
        self.assertEqual(catalog_signature(row.locator), row.signature)
        # A loaded player must not skip the chapter chooser.
        ready = self.wait_ready({PageKind.RESOURCES, PageKind.VIDEO})
        self.assertEqual(ready.kind, PageKind.RESOURCES)

    def test_shared_video_completion_uses_site_markers_and_preserves_unknown(self):
        self.page.goto(self.server.origin + SHARED)
        self.page.evaluate('''() => {
            const rows = document.querySelectorAll('.chapterScrollbar li.video');
            rows[0].insertAdjacentHTML('beforeend', '<b class="time_icofinish"></b>');
            rows[1].insertAdjacentHTML('beforeend', '<b class="time_ico_half"></b>'
                + '<div role="progressbar" aria-valuenow="27" aria-valuemax="100"></div>');
            rows[1].insertAdjacentHTML('afterend', '<li class="video">'
                + '<span class="cataloguediv-l">1.2</span><span class="catalogue_title">未知</span>'
                + '<span class="time">00:00:01</span><b class="time_ico_half"></b>'
                + '<div role="progressbar" aria-valuenow="" aria-valuemax="100"></div></li>');
        }''')
        probe = self.wait_ready({PageKind.RESOURCES})
        self.assertEqual([row.completed for row in probe.records], [True, False, None])

    def test_resource_completion_does_not_borrow_chapter_progress(self):
        self.page.goto(self.server.origin + RESOURCES)
        self.page.set_content('''<main>学习资源
            <div class="resource-item"><span>完成.mp4</span>
              <div role="progressbar" aria-valuenow="100" aria-valuemax="100"></div></div>
            <div class="resource-item"><span>未完成.mp4</span>
              <div role="progressbar" aria-valuenow="27" aria-valuemax="100"></div></div>
            <div class="resource-item"><div role="progressbar" aria-valuenow="0"></div>
              <div class="resource-item"><span>未知.mp4</span></div></div>
            </main>''')
        probe = self.wait_ready({PageKind.RESOURCES})
        self.assertEqual([row.completed for row in probe.records], [True, False, None])

    def test_tree_resource_records_use_leaf_rows_completion_and_play_target(self):
        self.page.goto(self.server.origin + RESOURCES)
        self.page.set_content('''<main>学习资源
          <div class="el-tree-node" role="treeitem"><div class="el-tree-node__content">第1章</div>
            <div role="group">
              <div class="el-tree-node" role="treeitem"><div class="el-tree-node__content custom-tree-node"><span class="file-name">完成.mp4 已完成</span><span class="el-checkbox success"></span></div></div>
              <div class="el-tree-node" role="treeitem"><div class="el-tree-node__content custom-tree-node"><span class="file-name">未完成.mp4 未完成</span><span class="el-checkbox info"></span></div></div>
              <div class="el-tree-node" role="treeitem"><div class="el-tree-node__content custom-tree-node"><span class="file-name">未知.mp4</span></div></div>
            </div>
          </div>
        </main>''')
        probe = self.adapter.probe_page(self.page)[0]
        self.assertEqual(probe.kind, PageKind.RESOURCES)
        self.assertEqual([row.completed for row in probe.records], [True, False, None])
        self.assertEqual([row.choice.label for row in probe.records], ['完成.mp4', '未完成.mp4', '未知.mp4'])
        self.assertTrue(all(row.locator.get_attribute('class').find('el-tree-node__content') >= 0
                            for row in probe.records))

    def test_shared_switch_waits_for_media_source_not_just_highlight(self):
        self.page.goto(self.server.origin + SHARED)
        probe = self.wait_ready({PageKind.RESOURCES})
        started = time.monotonic()
        ready = self.adapter.follow_click(
            self.context, self.page, probe.records[1], {PageKind.VIDEO}, 3,
            self.token, lambda *args: None, Phase.LOADING_VIDEO)
        self.assertEqual(ready.kind, PageKind.VIDEO)
        self.assertGreater(time.monotonic() - started, .6)
        self.assertIn('part=1', self.page.locator('video').get_attribute('src'))

    def test_same_name_course_cards_keep_type_with_long_teacher_list(self):
        self.goto('')
        self.page.set_content('<main>AI智慧课程中心 我学的课'
            '<section class="course-card"><span class="course-tag">AI智课</span>'
            '<div class="course-term">2026 秋冬</div><h4>马克思主义基本原理</h4>'
            '<p class="teacher-info">' + '测试老师、' * 100 + '</p></section>'
            '<section class="course-card"><span class="course-tag">共享课</span>'
            '<h4>马克思主义基本原理</h4><p class="teacher-info">张老师</p></section></main>')
        probe = self.wait_ready({PageKind.COURSES})
        self.assertIn('AI智课', probe.records[0].choice.detail)
        self.assertIn('2026 秋冬', probe.records[0].choice.detail)
        self.assertIn('共享课', probe.records[1].choice.detail)
        self.assertNotEqual(probe.records[0].choice.detail, probe.records[1].choice.detail)

    def test_changed_course_metadata_cannot_select_wrong_semester(self):
        self.goto("?case=duplicates")
        probe = self.wait_ready({PageKind.COURSES})
        probe.records[0].locator.evaluate(
            "element => {element.parentElement.querySelector('p').innerText = 'changed term';}"
        )
        with self.assertRaisesRegex(NavigationError, "发生变化"):
            self.adapter.follow_click(
                self.context, probe.page, probe.records[0], {PageKind.RESOURCES}, 1,
                self.token, lambda phase, message: None, Phase.LOADING_RESOURCES,
            )

    def test_stop_during_manual_login(self):
        self.page.goto(self.server.origin + "/login")
        timer = threading.Timer(0.2, self.token.cancel)
        timer.start()
        try:
            with self.assertRaises(UserCancelled):
                self.wait_ready({PageKind.COURSES}, 20)
        finally:
            timer.join(1)

    def test_headless_login_is_actionable(self):
        self.adapter.headless = True
        self.page.goto(self.server.origin + "/login")
        with self.assertRaisesRegex(LoginRequired, "可见浏览器"):
            self.wait_ready({PageKind.COURSES})

    def test_failed_navigation_is_bounded(self):
        self.goto("?case=missing")
        probe = self.wait_ready({PageKind.COURSES})
        with self.assertRaises(PageNotReady):
            self.adapter.follow_click(
                self.context, probe.page, probe.records[0], {PageKind.RESOURCES}, 0.4,
                self.token, lambda phase, message: None, Phase.LOADING_RESOURCES,
            )


@unittest.skipUnless(os.getenv("TREE_RUN_BROWSER_TESTS") == "1", "use --browser")
class WorkflowBrowserTests(unittest.TestCase):
    def run_fixture(self, mode, connection_mode='system'):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            events, selected = [], []
            def choose(title, choices, token):
                selected.append((title, choices[0].label))
                return choices[0].key
            settings = Settings(
                start_url=server.origin + CENTER + "?mode=" + mode,
                headless=True, login_timeout=5, page_timeout=5,
                video_timeout=8, stall_timeout=4, poll_interval=0.05,
                artifacts_dir=Path(folder), connection_mode=connection_mode,
            )
            adapter = ZhihuishuAdapter(True, 0.05, server.profile)
            outcome = Workflow(settings, choose, events.append, adapter=adapter).run()
            self.assertEqual(outcome.status, "complete", outcome.message)
            self.assertEqual(selected, [("课程", "新中国史"), ("视频", "绪论.mp4")])
            progress = [event.data for event in events if event.kind == "progress"]
            self.assertTrue(progress[-1]["ended"])
            self.assertGreater(progress[-1]["duration"], 0)
            self.assertTrue((Path(outcome.diagnostic_dir) / "events.jsonl").exists())
            self.assertTrue((Path(outcome.diagnostic_dir) / "result.json").exists())
            if connection_mode == 'direct':
                self.assertTrue(any(event.kind == 'log' and '直连' in event.data['message']
                                    for event in events))

    def test_real_video_popup_flow(self):
        self.run_fixture("popup")

    def test_real_video_same_tab_flow(self):
        self.run_fixture("same")

    def test_direct_browser_plays_full_local_flow(self):
        self.run_fixture('same', connection_mode='direct')

    def test_ai_course_notices_catalog_and_iframe_playback_flow(self):
        self.run_fixture("ai")

    def test_shared_course_multi_video_queue(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            selections, events = [], []
            def choose(title, choices, token):
                selections.append((title, [c.label for c in choices]))
                return [c.key for c in choices]
            settings = Settings(
                start_url=server.origin + CENTER + '?mode=shared', headless=True,
                login_timeout=5, page_timeout=5, video_timeout=8, stall_timeout=4,
                poll_interval=.05, artifacts_dir=Path(folder))
            result = Workflow(settings, choose, events.append,
                              adapter=ZhihuishuAdapter(True, .05, server.profile)).run()
            self.assertEqual(result.status, 'complete', result.message)
            self.assertEqual(selections, [('课程', ['新中国史']), ('视频', ['0.1 引言', '1.1 引言'])])
            ended = [e for e in events if e.kind == 'progress' and e.data['ended']]
            self.assertEqual(len(ended), 2)

    def test_completion_state_reaches_the_final_playback_plan(self):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            events = []
            def choose(title, choices, token):
                self.assertEqual(title, '视频')
                catalog = next(event.data for event in events if event.kind == 'catalog_ready')
                self.assertEqual([v['completed'] for v in catalog['groups'][0]['videos']], [True, False])
                self.assertIn('已完成', choices[0].detail)
                self.assertIn('未完成', choices[1].detail)
                return [choices[1].key]
            settings = Settings(start_url=server.origin + SHARED + '?case=completion', headless=True,
                                login_timeout=5, page_timeout=5, video_timeout=8, stall_timeout=4,
                                poll_interval=.05, artifacts_dir=Path(folder))
            outcome = Workflow(settings, choose, events.append,
                               adapter=ZhihuishuAdapter(True, .05, server.profile)).run()
            self.assertEqual(outcome.status, 'complete', outcome.message)
            played = [e.data['choice']['label'] for e in events
                      if e.kind == 'selected' and e.data['category'] == '视频']
            self.assertEqual(played, ['1.1 引言'])

    def run_batch(self, mode, case="batch", cancel=False):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            events = []
            token = CancellationToken()
            def emit(event):
                events.append(event)
                if cancel and event.kind == "queue" and event.data["completed"] == 1:
                    token.cancel()
            settings = Settings(
                start_url=server.origin + CENTER + f"?mode={mode}&case={case}",
                headless=True, login_timeout=5, page_timeout=5, video_timeout=8,
                stall_timeout=4, poll_interval=.05, artifacts_dir=Path(folder))
            outcome = Workflow(settings, lambda title, choices, token: [row.key for row in choices],
                               emit, token, ZhihuishuAdapter(True, .05, server.profile)).run()
            ended = [event for event in events if event.kind == "progress" and event.data["ended"]]
            self.assertEqual(outcome.status, "cancelled" if cancel else "complete", outcome.message)
            self.assertEqual(len(ended), 1 if cancel else 2 if case == "batchempty" else 4)
            if not cancel:
                queue = [event.data for event in events if event.kind == "queue"]
                self.assertEqual(queue[-1]["completed"], queue[-1]["total"])
            videos = [event.data["choice"]["label"] for event in events
                      if event.kind == "selected" and event.data["category"] == "视频"]
            self.assertEqual(videos, ["绪论.mp4"] if cancel else ["绪论.mp4", "结语.mp4"]
                             * (1 if case == "batchempty" else 2))

    def test_multi_course_multi_video_popup_queue(self):
        self.run_batch("popup")

    def test_multi_course_multi_video_same_tab_queue(self):
        self.run_batch("same")

    def test_empty_course_does_not_block_other_selected_courses(self):
        self.run_batch("same", "batchempty")

    def test_stop_queue_prevents_next_video(self):
        self.run_batch("popup", cancel=True)

    def run_speed(self, case, expected):
        with FixtureServer() as server, tempfile.TemporaryDirectory() as folder:
            events = []
            settings = Settings(
                start_url=server.origin + VIDEO + "?case=" + case, headless=True,
                playback_rate=2, login_timeout=5, page_timeout=5, video_timeout=8,
                stall_timeout=4, poll_interval=.05, artifacts_dir=Path(folder))
            outcome = Workflow(settings, lambda *args: self.fail("Direct video needs no chooser"),
                               events.append, adapter=ZhihuishuAdapter(True, .05, server.profile)).run()
            self.assertEqual(outcome.status, "complete", outcome.message)
            progress = [event.data for event in events if event.kind == "progress"]
            self.assertTrue(progress[-1]["ended"])
            self.assertEqual(progress[-1]["playback_rate"], expected)
            return [event.data["message"] for event in events if event.kind == "log"]

    def test_course_speed_menu_is_used(self):
        messages = self.run_speed("speed", 2)
        self.assertTrue(any("课程倍速菜单选择 2" in message for message in messages))

    def test_disabled_course_speed_option_uses_lower_allowed_rate(self):
        self.run_speed("speedlimited", 1.5)

    def test_hidden_course_speed_controls_are_not_forced(self):
        self.run_speed("speedhidden", 1)

    def test_course_without_speed_controls_stays_at_current_rate(self):
        self.run_speed("plain", 1)

    def test_course_speed_reset_is_respected(self):
        messages = self.run_speed("speedreset", 1)
        self.assertTrue(any("速度已变为 1" in message for message in messages))

    def test_in_video_quiz_popup_is_answered_and_playback_resumes(self):
        for case in ("quiz", "aiquiz"):
            with self.subTest(case=case):
                messages = self.run_speed(case, 1)
                self.assertTrue(any("课中弹题" in message for message in messages))
