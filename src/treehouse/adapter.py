"""Visible-DOM adapter. A URL alone never establishes authentication."""
import re
import time
from hashlib import sha256
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .cancellation import CancellationToken
from .diagnostics import safe_url
from .errors import CatalogUnavailable, LoginRequired, NavigationError, PageNotReady, UserCancelled
from .models import Choice, PageKind, Phase


@dataclass(frozen=True)
class SiteProfile:
    center_host: str = "hike-teaching-center.polymas.com"
    resource_host: str = "wenda.zhihuishu.com"
    video_host: str = "hike.zhihuishu.com"
    auth_hosts: tuple[str, ...] = ("login.zhihuishu.com", "cloudapi.polymas.com")
    auth_paths: tuple[str, ...] = ()
    center_path: str = "/stu-hike/agent-course-hike/ai-course-center"
    resource_path: str = "/stu/courseInfo/studyResource"
    video_path: str = "/aidedteaching/sourceLearning/sourceLearning"
    shared_host: str = "studyvideoh5.zhihuishu.com"
    shared_path: str = "/stuStudy"


@dataclass
class CatalogRecord:
    choice: Choice
    locator: object
    signature: str = ""
    completed: bool | None = None


@dataclass
class PageProbe:
    page: object
    scope: object
    kind: PageKind
    url: str
    title: str = ""
    records: list[CatalogRecord] = field(default_factory=list)
    visible_inputs: int = 0
    login_marker: bool = False

    def serializable(self) -> dict:
        return {
            "url": safe_url(self.url), "title": self.title, "kind": self.kind.value,
            "items": len(self.records), "visible_inputs": self.visible_inputs,
            "login_marker": self.login_marker,
        }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\ue000-\uf8ff]", "", text)).strip()


def catalog_signature(locator) -> str:
    raw = locator.evaluate("""e => {
        if (e.matches('li.video') && e.closest('.chapterScrollbar')) {
            // Progress and current_play change during playback, not identity.
            return ['shared-video', '.cataloguediv-l', '.catalogue_title', '.time']
                .map(s => s === 'shared-video' ? s : e.querySelector(s)?.textContent || '')
                .join('\\n');
        }
        return [
        e.getAttribute('id') || '', e.getAttribute('href') || '',
        e.innerText, e.parentElement ? e.parentElement.innerText : ''
    ].join('\\n'); }""")
    return sha256(normalize_text(raw).encode("utf-8")).hexdigest()


def resource_title(text: str) -> str | None:
    text = re.sub(r"[\ue000-\uf8ff]", "", text)
    match = re.search(r"([^\r\n]*?\.mp4)\b", text, re.IGNORECASE)
    return normalize_text(match.group(1)) if match else None


class ZhihuishuAdapter:
    def __init__(self, headless=False, poll_interval=0.2, profile=None, credentials=None,
                 login_hook=None):
        self.login_hook = login_hook
        self.credentials = credentials or ("", "")
        self.headless = headless
        self.poll_interval = poll_interval
        self.profile = profile or SiteProfile()

    @staticmethod
    def _visible(locator) -> list:
        # Snapshot only: callers poll until explicit readiness before presenting it.
        return [item for item in locator.all() if item.is_visible()]

    def autofill_login(self, scope) -> None:
        """Fill only empty account/password boxes; captcha, agreement and submit stay manual."""
        username, password = self.credentials
        if not username and not password:
            return
        try:
            for placeholder, value in (("请输入手机号或用户名", username), ("请输入密码", password)):
                if not value:
                    continue
                box = scope.get_by_placeholder(placeholder).first
                if box.count() and box.is_visible() and not box.input_value():
                    box.fill(value, timeout=1000)
        except Exception:
            # Login page may be mid-render or on another tab; the user can type manually.
            pass

    def course_records(self, scope) -> list[CatalogRecord]:
        records = []
        for index, item in enumerate(self._visible(scope.get_by_role("heading", level=4))):
            label = normalize_text(item.inner_text())
            if not label:
                continue
            detail = item.evaluate(
                """e => {
                    const card = e.closest('.course-card');
                    if (!card) return e.parentElement ? e.parentElement.innerText : '';
                    const fields = ['.course-tag', '.course-term', '.type-tag-component'];
                    const info = fields.map(s => card.querySelector(s)?.innerText || '');
                    const teacher = card.querySelector('.teacher-info')?.innerText.trim();
                    if (teacher) info.push('教师：' + teacher.slice(0, 70));
                    return info.filter(Boolean).join(' · ');
                }"""
            )
            detail = normalize_text(detail).replace(label, "", 1).strip()
            detail = detail[:240]
            records.append(CatalogRecord(
                Choice(f"course:{index}", label, detail), item, catalog_signature(item)
            ))
        return records

    def is_shared_course(self, url) -> bool:
        parsed = urlsplit(url)
        return (parsed.hostname == self.profile.shared_host
                and parsed.path.rstrip('/') == self.profile.shared_path)

    def shared_resource_records(self, scope) -> list[CatalogRecord]:
        records = []
        for index, row in enumerate(self._visible(scope.locator('.chapterScrollbar li.video'))):
            title = row.locator('.catalogue_title').inner_text()
            order = normalize_text(row.locator('.cataloguediv-l').inner_text())
            duration = normalize_text(row.locator('.time').inner_text())
            title = normalize_text(title)
            if title:
                label = normalize_text(f'{order} {title}')
                completed = row.evaluate("""e => {
                    if (e.querySelector('.time_icofinish')) return true;
                    const bar = e.querySelector('[role="progressbar"][aria-valuenow]');
                    if (bar) {
                        const raw = bar.getAttribute('aria-valuenow').trim();
                        const value = Number(raw);
                        const max = Number(bar.getAttribute('aria-valuemax') || 100);
                        if (raw && Number.isFinite(value) && Number.isFinite(max)
                                && max > 0 && value >= 0 && value <= max) return value >= max;
                        return null;
                    }
                    // This icon is present on the site's known unstarted rows.
                    return e.querySelector('.time_ico_half') ? false : null;
                }""")
                records.append(CatalogRecord(
                    Choice(f'shared-video:{index}', label, f'共享课 · {duration}'),
                    row, catalog_signature(row), completed))
        return records

    def resource_records(self, scope) -> list[CatalogRecord]:
        records = []
        mp4_re = re.compile(r"\.mp4\b", re.IGNORECASE)
        tree_items = self._visible(scope.locator('[role="treeitem"]'))
        candidates = []
        for item in tree_items:
            if item.locator('[role="treeitem"]').count() == 0 and mp4_re.search(item.inner_text()):
                candidates.append(item)
        if not candidates:
            candidates = self._visible(scope.get_by_text(mp4_re))
        for index, item in enumerate(candidates):
            raw_text = item.inner_text()
            label = resource_title(raw_text)
            if not label:
                continue
            detail = normalize_text(raw_text).replace(label, "", 1).strip()[:240]
            completed = item.evaluate("""e => {
                const row = e.closest('.resource-item')
                    || (e.matches('[role="treeitem"]') ? e : e.parentElement);
                if (!row) return null;
                // A chapter container can contain several resources; its
                // progress must not be attributed to a particular video.
                if (row.matches('.resource-item') && row.querySelector('.resource-item')) return null;
                const lines = (row.innerText || '').split(/\\r?\\n/).map(s => s.trim());
                if (lines.includes('已完成')) return true;
                if (lines.includes('未完成')) return false;
                const checkbox = row.querySelector('.el-checkbox');
                if (checkbox) {
                    if (checkbox.classList.contains('success')) return true;
                    if (checkbox.classList.contains('info')) return false;
                }
                const bar = row.querySelector('[role="progressbar"][aria-valuenow]');
                if (!bar) return null;
                const raw = bar.getAttribute('aria-valuenow').trim();
                const value = Number(raw);
                const max = Number(bar.getAttribute('aria-valuemax') || 100);
                return raw && Number.isFinite(value) && Number.isFinite(max)
                    && max > 0 && value >= 0 && value <= max ? value >= max : null;
            }""")
            click_target = item
            for selector in (".file-name", ".custom-tree-node", ".el-tree-node__content"):
                inner = self._visible(item.locator(selector))
                if inner:
                    click_target = inner[0]
                    break
            # Identical filenames are retained as distinct rows, not silently dropped.
            records.append(CatalogRecord(
                Choice(f"video:{index}", label, detail), click_target, catalog_signature(click_target), completed
            ))
        return records

    def _probe_scope(self, page, scope, title) -> PageProbe:
        url = scope.url or page.url
        parsed = urlsplit(url)
        main = urlsplit(page.url)
        probe = PageProbe(page, scope, PageKind.LOADING, url, title)
        text = scope.locator("body").inner_text(timeout=700)
        probe.visible_inputs = scope.locator("input:visible").count()
        probe.login_marker = any(marker in text for marker in (
            "发送验证码", "立即注册", "通过微信登录", "我已阅读并同意",
        ))
        if (parsed.hostname in self.profile.auth_hosts
                or parsed.path in self.profile.auth_paths
                or (probe.visible_inputs and probe.login_marker)):
            probe.kind = PageKind.LOGIN
            return probe

        host, path = main.hostname, main.path.rstrip("/")
        is_center = host == self.profile.center_host and path == self.profile.center_path
        is_resources = host == self.profile.resource_host and path == self.profile.resource_path
        is_video = host == self.profile.video_host and path == self.profile.video_path
        is_ai_video = host == self.profile.center_host and bool(re.search(
            r"/agent-course-full/[^/]+/[^/]+/[^/]+/[^/]+/stu/study/resource-detail$", path
        ))
        is_home = host == self.profile.center_host and bool(re.search(
            r"/agent-course-full/[^/]+/stu/course-home$", path
        ))
        is_study = host == self.profile.center_host and bool(re.search(
            r"/agent-course-full/[^/]+/stu/study$", path
        ))

        if self.is_shared_course(url):
            probe.records = self.shared_resource_records(scope)
            if probe.records:
                probe.kind = PageKind.RESOURCES
        elif is_center:
            probe.records = self.course_records(scope)
            if probe.records and any(marker in text for marker in ("我学的课", "AI智慧课程中心")):
                probe.kind = PageKind.COURSES
        elif is_resources or is_study:
            probe.records = self.resource_records(scope)
            if probe.records:
                probe.kind = PageKind.RESOURCES
        elif is_video or is_ai_video:
            if self._visible(scope.locator("video")):
                probe.kind = PageKind.VIDEO
        elif is_home:
            if "我的学习" in text and "课程主页" in text:
                probe.kind = PageKind.COURSE_HOME
        else:
            probe.kind = PageKind.UNKNOWN

        catalog_marker = any(marker in text for marker in (
            "我学的课", "学习资源", "我的学习", "AI智慧课程中心",
        ))
        explicit_empty = bool(re.search(
            r"暂无(?:数据|课程|资源)|没有课程|共\s*0\s*个学习资源", text
        ))
        if (is_center or is_resources or is_study) and not probe.records and catalog_marker and explicit_empty:
            probe.kind = PageKind.EMPTY
        return probe

    def dismiss_course_notices(self, page):
        """Dismiss only the known non-binding AI course onboarding notices."""
        if self.is_shared_course(page.url):
            # Do not bind an account, subscribe, acknowledge a risk warning,
            # answer a question or touch a verification challenge.
            for selector in (
                '.dialog-warn [aria-label="课程提醒"] .talk-later-btn',
                '.dialog-read .el-dialog__header .iconguanbi',
                '.read-learn [aria-label="学前必读"] .el-dialog__headerbtn',
            ):
                buttons = self._visible(page.locator(selector))
                if len(buttons) == 1:
                    buttons[0].click(timeout=1500)
            return
        parsed = urlsplit(page.url)
        if (parsed.hostname != self.profile.center_host or not re.search(
                r"/agent-course-full/[^/]+/stu/(?:course-home|study)$", parsed.path)):
            return
        # The guide and semester dialog can both say 我知道了. Handle the
        # guide first instead of clicking an ambiguous page-wide text match.
        guides = self._visible(page.locator(".driver-popover .driver-popover-done-btn"))
        if len(guides) == 1 and normalize_text(guides[0].inner_text()) == "我知道了":
            guides[0].click(timeout=1500)
        notices = self._visible(page.get_by_text(
            "平台进入新学期后，您可以切换历史学期查看教学数据", exact=True))
        if len(notices) == 1:
            buttons = self._visible(page.get_by_text("我知道了", exact=True))
            if len(buttons) == 1:
                buttons[0].click(timeout=1500)

    def probe_page(self, page) -> list[PageProbe]:
        probes = []
        try:
            self.dismiss_course_notices(page)
        except Exception:
            # Animation/navigation can interrupt a notice; retry on the next poll.
            pass
        try:
            title = page.title()
        except Exception:
            title = ""
        for scope in page.frames:
            try:
                probe = self._probe_scope(page, scope, title)
                probes.append(probe)
                # A shared-course page contains both the catalog and player.
                # Present the catalog first, and expose VIDEO for playback waits.
                if (self.is_shared_course(scope.url)
                        and self._visible(scope.locator('video'))):
                    probes.append(PageProbe(page, scope, PageKind.VIDEO, scope.url, title))
            except Exception:
                # Redirects detach frames. They are loading, never authenticated.
                probes.append(PageProbe(page, scope, PageKind.LOADING, page.url, title))
        return probes

    def wait_ready(self, context, allowed, timeout, token, phase_callback,
                   preferred=None, loading_phase=Phase.WAITING_PAGE) -> PageProbe:
        deadline = time.monotonic() + timeout
        seen_login = False
        stable_key = None
        stable_count = 0
        last_phase = None
        while True:
            token.check()
            pages = [page for page in context.pages if not page.is_closed()]
            if preferred is not None:
                pages = [page for page in pages if preferred(page)]
            if not pages:
                raise NavigationError("浏览器页面已关闭。")
            probes = [probe for page in reversed(pages) for probe in self.probe_page(page)]
            ready = next((probe for probe in probes if probe.kind in allowed), None)
            if ready:
                key = (id(ready.page), ready.kind, ready.url, tuple(
                    row.choice.label for row in ready.records
                ))
                stable_count = stable_count + 1 if key == stable_key else 1
                stable_key = key
                required_stable = 15 if ready.kind == PageKind.EMPTY else 2
                if stable_count >= required_stable:
                    if self.login_hook:
                        self.login_hook.close()
                    return ready
            else:
                stable_key, stable_count = None, 0
            login = any(probe.kind == PageKind.LOGIN for probe in probes)
            if login and (not self.headless or self.login_hook):
                for probe in probes:
                    if probe.kind == PageKind.LOGIN:
                        self.autofill_login(probe.scope)
            if self.login_hook and not login and last_phase == Phase.WAITING_LOGIN:
                self.login_hook.close()
            seen_login |= login
            phase = Phase.WAITING_LOGIN if login else loading_phase
            if phase != last_phase:
                if login:
                    phase_callback(phase, "请在软件弹出的登录窗口中完成验证码并点击登录。" if self.login_hook
                                   else "请在打开的浏览器中手动登录并完成验证码，程序正在等待。")
                    if self.headless and not self.login_hook:
                        raise LoginRequired(
                            "登录态不可用。请用可见浏览器完成人工登录，再选择保存的登录态进行无头运行。"
                        )
                else:
                    phase_callback(phase, "正在等待页面内容加载。")
                last_phase = phase
            if time.monotonic() >= deadline:
                if seen_login:
                    raise LoginRequired("尚未完成登录，等待已超时。可增加登录等待时间后重试。")
                raise PageNotReady("页面未在限定时间内显示课程、资源或播放器。请查看诊断记录。")
            # Pump Playwright's event loop while the SPA or popup is changing.
            if login and self.login_hook:
                login_page = next(p.page for p in probes if p.kind == PageKind.LOGIN)
                try:
                    self.login_hook.pump(login_page)
                    continue
                except Exception:
                    token.check()
            try:
                pages[-1].wait_for_timeout(self.poll_interval * 1000)
            except Exception:
                token.check()
                if not any(not page.is_closed() for page in context.pages):
                    raise NavigationError("浏览器页面已关闭。") from None

    def follow_click(self, context, origin, record, allowed, timeout, token, callback,
                     loading_phase) -> PageProbe:
        token.check()
        if record.signature and catalog_signature(record.locator) != record.signature:
            raise NavigationError("选择期间目录项目发生变化，请重新扫描后选择。")
        if record.choice.label not in normalize_text(record.locator.inner_text()):
            raise NavigationError("选择的项目已发生变化，请重新扫描页面。")
        previous_pages = {id(page) for page in context.pages}
        shared_video = record.choice.key.startswith('shared-video:')
        old_source, was_current = '', False
        if shared_video:
            self.dismiss_course_notices(origin)
            was_current = 'current_play' in (record.locator.get_attribute('class') or '').split()
            videos = self._visible(origin.locator('video'))
            if len(videos) == 1:
                old_source = videos[0].evaluate('v => v.currentSrc || v.src')
        # Re-clicking an already active shared lesson can schedule an async
        # reload that pauses the player after VideoPlayer has started it.
        if not (shared_video and was_current):
            record.locator.click(timeout=timeout * 1000)
        if shared_video:
            deadline = time.monotonic() + timeout
            while True:
                token.check()
                current = 'current_play' in (record.locator.get_attribute('class') or '').split()
                videos = self._visible(origin.locator('video'))
                source = videos[0].evaluate('v => v.currentSrc || v.src') if len(videos) == 1 else ''
                if current and source and (was_current or source != old_source):
                    break
                if time.monotonic() >= deadline:
                    raise PageNotReady('共享课未切换到所选视频。请检查课程提示或人工验证。')
                origin.wait_for_timeout(self.poll_interval * 1000)
        return self.wait_ready(
            context, allowed, timeout, token, callback,
            preferred=lambda page: page is origin or id(page) not in previous_pages,
            loading_phase=loading_phase,
        )

    def open_study(self, context, probe, timeout, token, callback) -> PageProbe:
        candidates = self._visible(probe.scope.get_by_text("我的学习", exact=True))
        if len(candidates) != 1:
            raise CatalogUnavailable("该课程主页没有可唯一定位的“我的学习”入口。")
        record = CatalogRecord(Choice("study", "我的学习"), candidates[0])
        return self.follow_click(
            context, probe.page, record,
            {PageKind.RESOURCES, PageKind.EMPTY, PageKind.VIDEO},
            timeout, token, callback, Phase.LOADING_RESOURCES,
        )

    def _answer_quiz_question(self, dialog, page, token=None) -> bool:
        if token is not None:
            token.check()
        if self._visible(dialog.locator(
                ".answer, .topic-item.active, .topic-item .active, "
                ".option.active, .option.is-checked")):
            return True
        options = self._visible(dialog.locator(".topic-item, .option"))
        if not options:
            return False
        options[0].click(timeout=1500)
        page.wait_for_timeout(100)
        return True

    def _dismiss_scope_quiz_popup(self, page, scope, token=None) -> bool:
        if not self._visible(scope.locator(
                ".dialog-test, .dialog-img, .ai-class-exercise-dialog")):
            return False

        for dialog in self._visible(scope.locator(".dialog-test")):
            numbers = self._visible(dialog.locator(".el-pager .number, .number"))
            if numbers:
                for index in range(len(numbers)):
                    if token is not None:
                        token.check()
                    current = self._visible(dialog.locator(".el-pager .number, .number"))
                    if index < len(current):
                        button = current[index]
                        if (len(current) > 1
                                and "active" not in (button.get_attribute("class") or "").split()):
                            button.click(timeout=1500)
                            page.wait_for_timeout(100)
                    self._answer_quiz_question(dialog, page, token)
            else:
                self._answer_quiz_question(dialog, page, token)
            close_buttons = self._visible(dialog.locator(
                ".el-dialog__footer .btn, .dialog-footer .btn, .el-dialog__headerbtn"
            ))
            if close_buttons:
                if token is not None:
                    token.check()
                close_buttons[0].click(timeout=1500)
                return True

        for dialog in self._visible(scope.locator(".dialog-img")):
            close_buttons = self._visible(dialog.locator(
                ".el-dialog__headerbtn, .el-dialog__footer .btn, .dialog-footer .btn"
            ))
            if close_buttons:
                if token is not None:
                    token.check()
                close_buttons[0].click(timeout=1500)
                return True

        for dialog in self._visible(scope.locator(".ai-class-exercise-dialog")):
            self._answer_quiz_question(dialog, page, token)
            submit_buttons = self._visible(dialog.locator(
                ".el-dialog__footer button.el-button, .el-dialog__footer .btn, .el-dialog__headerbtn"
            ))
            if submit_buttons:
                if token is not None:
                    token.check()
                submit_buttons[0].click(timeout=1500)
                return True

        return False

    def dismiss_quiz_popup(self, page, token=None) -> bool:
        """Answer and close known non-graded in-video quiz popups during playback."""
        try:
            for scope in page.frames:
                if token is not None:
                    token.check()
                if self._dismiss_scope_quiz_popup(page, scope, token):
                    return True
        except UserCancelled:
            raise
        except Exception:
            if token is not None:
                token.check()
        return False

    def video_locator(self, page):
        candidates = []
        for scope in page.frames:
            for item in self._visible(scope.locator("video")):
                candidates.append((scope, item))
        if len(candidates) != 1:
            raise CatalogUnavailable(f"课程播放页应有一个可见视频，实际找到 {len(candidates)} 个。")
        return candidates[0]
