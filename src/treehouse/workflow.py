from dataclasses import asdict, dataclass

from .adapter import CatalogRecord, ZhihuishuAdapter
from .cancellation import CancellationToken
from .config import Settings
from .diagnostics import Diagnostics
from .errors import CatalogUnavailable, DependencyError, NavigationError, PlayerError, UserCancelled
from .models import Choice, Event, Outcome, PageKind, Phase
from .network import network_error_message
from .player import VideoPlayer


@dataclass(frozen=True)
class VideoJob:
    course: object
    resource_url: str
    video: object
    signature: str = ""
    direct: bool = False
    completed: bool | None = None


class Workflow:
    def __init__(self, settings: Settings, choose, emit=lambda event: None,
                 token=None, adapter=None):
        self.settings = settings.validate()
        self.choose = choose
        self.emit_callback = emit
        self.token = token or CancellationToken()
        self.adapter = adapter or ZhihuishuAdapter(
            settings.headless, settings.poll_interval
        )
        self.diagnostics = None
        self.last_phase = None

    def emit(self, kind, **data):
        event = Event(kind, data)
        if self.diagnostics:
            self.diagnostics.event(kind, data)
        self.emit_callback(event)

    def phase(self, phase, message):
        if phase != self.last_phase:
            self.last_phase = phase
            if self.diagnostics:
                self.diagnostics.logger.info("%s: %s", phase.value, message)
            self.emit("phase", phase=phase.value, message=message)
            self.emit("log", message=message)

    def select_records(self, title, records):
        if not records:
            raise CatalogUnavailable("页面没有可选择的项目。")
        self.token.check()
        choices = [record.choice for record in records]
        selected = self.choose(title, choices, self.token)
        self.token.check()
        keys = [selected] if isinstance(selected, str) else selected
        if (not isinstance(keys, (list, tuple)) or not keys
                or any(not isinstance(key, str) or key not in {row.choice.key for row in records}
                       for key in keys)):
            raise UserCancelled("选择已取消或失效。")
        records = [record for record in records if record.choice.key in keys]
        self.emit("log", message=f"已选择{len(records)}个{title}：" + "、".join(
            record.choice.label for record in records))
        return records

    def selected(self, title, record):
        self.emit("selected", category=title, choice=asdict(record.choice))

    @staticmethod
    def match_record(records, choice, signature):
        # Keys contain DOM indices and cannot identify a row after a reload.
        matches = [record for record in records if record.choice.label == choice.label
                   and record.choice.detail == choice.detail
                   and (not signature or record.signature == signature)]
        if len(matches) != 1:
            raise NavigationError(f"目录中的“{choice.label}”已变化或无法唯一定位，请重新选择。")
        return matches[0]

    def open_url(self, context, page, url, allowed):
        self.token.check()
        response = page.goto(url, wait_until="domcontentloaded")
        if response and response.status >= 400:
            raise NavigationError(f"队列页面返回 HTTP {response.status}。")
        return self.adapter.wait_ready(
            context, allowed, self.settings.login_timeout, self.token, self.phase,
            preferred=lambda candidate: candidate is page,
        )

    @staticmethod
    def close_extra_pages(context, keep):
        for page in list(context.pages):
            if page is not keep and not page.is_closed():
                page.close()

    def collect_jobs(self, context, probe, course=None):
        if probe.kind == PageKind.COURSE_HOME:
            probe = self.adapter.open_study(
                context, probe, self.settings.page_timeout, self.token, self.phase)
        if probe.kind == PageKind.EMPTY:
            self.emit("log", message="该课程明确没有学习资源，已跳过。")
            return []
        if probe.kind == PageKind.VIDEO:
            from .models import Choice
            return [VideoJob(course, probe.page.url, Choice("direct", probe.title or "课程视频"), direct=True)]
        if probe.kind != PageKind.RESOURCES:
            raise CatalogUnavailable("没有进入受支持的课程资源页。")
        return [VideoJob(course, probe.page.url, row.choice, row.signature, completed=row.completed)
                for row in probe.records]

    def review_queue(self, groups):
        """Scan every selected course first, then ask for one final playback plan."""
        jobs, records, catalogs = [], [], []
        for index, (course, course_jobs) in enumerate(groups):
            videos = []
            for job in course_jobs:
                key = f'plan:{len(jobs)}'
                status = ('已完成' if job.completed is True else
                          '未完成' if job.completed is False else '状态未知')
                detail = ' · '.join(filter(None, (
                    course.label if course else '', course.detail if course else '', job.video.detail, status)))
                records.append(CatalogRecord(Choice(key, job.video.label, detail), None))
                videos.append({'key': key, 'label': job.video.label, 'detail': job.video.detail,
                               'signature': job.signature, 'completed': job.completed})
                jobs.append(job)
            catalogs.append({'key': f'scan:{index}',
                             'course': asdict(course) if course else {'key': 'direct', 'label': '当前课程'},
                             'videos': videos, 'status': 'ready' if videos else 'empty'})
        self.emit('catalog_ready', groups=catalogs, total=len(jobs))
        if not jobs:
            raise CatalogUnavailable('所选课程没有可播放的视频资源。可以重新选择其他课程。')
        self.phase(Phase.CHOOSING_VIDEO, '资源扫描完成。请勾选视频，点击“开始播放”后启动队列。')
        selected = self.select_records('视频', records)
        keys = {record.choice.key for record in selected}
        return [job for index, job in enumerate(jobs) if f'plan:{index}' in keys]

    def build_queue(self, context, origin, probe):
        if probe.kind != PageKind.COURSES:
            jobs = self.collect_jobs(context, probe)
            return jobs if probe.kind == PageKind.VIDEO else self.review_queue([(None, jobs)])
        self.phase(Phase.CHOOSING_COURSE, "课程列表已加载，可多选课程。")
        courses = self.select_records("课程", probe.records)
        center_url, groups = probe.page.url, []
        for index, course in enumerate(courses):
            self.token.check()
            if index:
                probe = self.open_url(context, origin, center_url, {PageKind.COURSES})
            current = self.match_record(probe.records, course.choice, course.signature)
            self.selected("课程", current)
            self.phase(Phase.LOADING_RESOURCES, f"正在读取课程 {index + 1}/{len(courses)}：{course.choice.label}")
            self.emit('scan_progress', current=index + 1, total=len(courses),
                      course=asdict(course.choice), message='正在扫描视频目录，不会开始播放。')
            resource = self.adapter.follow_click(
                context, probe.page, current,
                {PageKind.RESOURCES, PageKind.COURSE_HOME, PageKind.VIDEO, PageKind.EMPTY},
                self.settings.login_timeout, self.token, self.phase, Phase.LOADING_RESOURCES)
            course_jobs = self.collect_jobs(context, resource, course.choice)
            groups.append((course.choice, course_jobs))
            self.emit('scan_progress', current=index + 1, total=len(courses),
                      course=asdict(course.choice), count=len(course_jobs),
                      message=f'已找到 {len(course_jobs)} 个视频')
            self.close_extra_pages(context, origin)
        return self.review_queue(groups)

    def play_queue(self, context, origin, jobs):
        if not jobs:
            raise CatalogUnavailable("所选课程没有可播放的视频资源。")
        self.emit("log", message=f"播放队列已建立，共 {len(jobs)} 个视频，将依次正常播放。")
        for index, job in enumerate(jobs):
            self.token.check()
            if job.course:
                self.emit("selected", category="课程", choice=asdict(job.course))
            self.emit("selected", category="视频", choice=asdict(job.video))
            self.emit("queue", completed=index, total=len(jobs), current=index + 1)
            self.phase(Phase.LOADING_VIDEO, f"正在加载视频 {index + 1}/{len(jobs)}：{job.video.label}")
            probe = self.open_url(context, origin, job.resource_url,
                                  {PageKind.VIDEO} if job.direct else {PageKind.RESOURCES, PageKind.EMPTY})
            if not job.direct:
                record = self.match_record(probe.records, job.video, job.signature)
                probe = self.adapter.follow_click(
                    context, probe.page, record, {PageKind.VIDEO, PageKind.EMPTY},
                    self.settings.page_timeout, self.token, self.phase, Phase.LOADING_VIDEO)
            if probe.kind != PageKind.VIDEO:
                raise CatalogUnavailable("没有进入受支持的课程视频播放页。")
            _, locator = self.adapter.video_locator(probe.page)
            self.phase(Phase.PLAYING, f"正在播放 {index + 1}/{len(jobs)}：{job.video.label}")
            VideoPlayer(
                self.settings, self.token,
                lambda progress: self.emit("progress", **progress),
                lambda message: self.emit("log", message=message),
                self.adapter.dismiss_quiz_popup,
            ).play(probe.page, locator)
            self.emit("log", message=f"已自然播放结束 {index + 1}/{len(jobs)}：{job.video.label}")
            self.emit("queue", completed=index + 1, total=len(jobs), current=index + 1)
            self.close_extra_pages(context, origin)
        self.phase(Phase.COMPLETE, f"队列完成：{len(jobs)} 个视频均已自然播放结束。")
        return self.finish("complete", f"队列完成：{len(jobs)} 个视频均已自然播放结束。")

    def finish(self, status, message):
        outcome = Outcome(status, message, str(self.diagnostics.path))
        self.diagnostics.outcome(outcome)
        return outcome

    @staticmethod
    def _playwright():
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError as error:
            raise DependencyError(
                "缺少 Playwright。请先执行 python -m pip install -r requirements.txt。"
            ) from error

    def run(self) -> Outcome:
        self.diagnostics = Diagnostics(self.settings.artifacts_dir)
        context = browser = None
        try:
            self.phase(Phase.STARTING, "正在启动浏览器。")
            sync_playwright = self._playwright()
            with sync_playwright() as playwright:
                try:
                    self.token.check()
                    launch_options = dict(headless=self.settings.headless,
                                          executable_path=self.settings.executable(),
                                          timeout=self.settings.page_timeout * 1000)
                    if self.settings.connection_mode == 'direct':
                        launch_options['args'] = ['--no-proxy-server']
                        self.emit('log', message='本次浏览器使用直连，不使用系统代理。')
                    browser = playwright.chromium.launch(**launch_options)
                    context = browser.new_context(
                        storage_state=str(self.settings.state_path) if self.settings.state_path else None
                    )
                    context.set_default_timeout(self.settings.page_timeout * 1000)
                    context.set_default_navigation_timeout(self.settings.page_timeout * 1000)
                    page = context.new_page()
                    response = page.goto(self.settings.start_url, wait_until="domcontentloaded")
                    if response and response.status >= 400:
                        raise PlayerError(f"页面返回 HTTP {response.status}。")
                    probe = self.adapter.wait_ready(
                        context, {PageKind.COURSES, PageKind.RESOURCES, PageKind.VIDEO,
                                  PageKind.COURSE_HOME, PageKind.EMPTY},
                        self.settings.login_timeout, self.token, self.phase,
                    )
                    if self.settings.save_state_path:
                        target = self.settings.save_state_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        context.storage_state(path=str(target), indexed_db=True)
                        self.emit("session_saved", path=str(target))
                        self.emit("log", message="已将登录态保存到你选择的本地文件。")
                    jobs = self.build_queue(context, page, probe)
                    return self.play_queue(context, page, jobs)
                except Exception as error:
                    if not isinstance(error, UserCancelled):
                        self.diagnostics.record_pages(context, self.adapter, error)
                    raise
                finally:
                    if browser:
                        try:
                            browser.close()
                        except Exception as close_error:
                            self.diagnostics.logger.warning("关闭浏览器：%s", close_error)
        except UserCancelled as error:
            self.phase(Phase.CANCELLED, str(error))
            return self.finish("cancelled", str(error))
        except Exception as error:
            self.diagnostics.logger.exception("流程失败")
            message = str(error) if isinstance(error, PlayerError) else (
                network_error_message(error) or "浏览器流程发生异常，请查看运行日志和诊断文件。"
            )
            if "Executable doesn't exist" in str(error):
                message = "缺少 Chromium。请执行 python -m playwright install chromium。"
            elif "has been closed" in str(error):
                message = "浏览器窗口已被关闭。"
            self.phase(Phase.ERROR, message)
            return self.finish("error", message)
        finally:
            self.diagnostics.close()
