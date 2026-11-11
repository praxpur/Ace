import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ConfigurationError
from .network import CONNECTION_MODES

def application_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "treehouse").is_dir():
        return candidate
    user_data = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME")
    return (Path(user_data) if user_data else Path.home() / ".local" / "share") / "Treehouse"


PROJECT_ROOT = application_root()
DEFAULT_STATE_PATH = PROJECT_ROOT / ".state" / "auth.json"
PLAYBACK_RATES = (1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0)
COURSE_CENTER_URL = (
    "https://hike-teaching-center.polymas.com/"
    "stu-hike/agent-course-hike/ai-course-center"
)


@dataclass(frozen=True)
class Settings:
    start_url: str = COURSE_CENTER_URL
    headless: bool = False
    login_timeout: float = 300.0
    page_timeout: float = 30.0
    video_timeout: float = 7200.0
    stall_timeout: float = 60.0
    poll_interval: float = 0.2
    muted: bool = True
    playback_rate: float = 1.0
    state_path: Path | None = None
    save_state_path: Path | None = None
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    browser_executable: Path | None = None
    connection_mode: str = 'system'
    embedded_login: bool = False
    username: str = ''
    password: str = field(default='', repr=False)

    def validate(self) -> "Settings":
        parsed = urlsplit(self.start_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConfigurationError("课程入口必须是有效的 HTTP 或 HTTPS 地址。")
        if parsed.username or parsed.password:
            raise ConfigurationError("课程入口不能包含账号或密码。")
        try:
            parsed.port
        except ValueError as error:
            raise ConfigurationError("课程入口端口无效。") from error
        for name in ("login_timeout", "page_timeout", "video_timeout", "stall_timeout", "poll_interval"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < float("inf"):
                raise ConfigurationError(f"{name} 必须是有限正数。")
        for name in ("headless", "muted", "embedded_login"):
            if type(getattr(self, name)) is not bool:
                raise ConfigurationError(f"{name} 必须是布尔值。")
        if (type(self.playback_rate) not in (int, float)
                or self.playback_rate not in PLAYBACK_RATES):
            raise ConfigurationError("播放速度必须是 1、1.25、1.5、1.75、2、3 或 4 倍。")
        if self.connection_mode not in CONNECTION_MODES:
            raise ConfigurationError('连接方式必须是跟随系统代理或直接连接。')
        if self.state_path and not self.state_path.is_file():
            raise ConfigurationError("选择的登录态文件不存在。")
        if self.state_path:
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
                if not isinstance(state, dict) or not isinstance(state.get("cookies"), list):
                    raise ValueError
                if not isinstance(state.get("origins", []), list):
                    raise ValueError
            except (OSError, ValueError) as error:
                raise ConfigurationError("登录态文件不是有效的 Playwright storage_state JSON。") from error
        if self.browser_executable and not self.browser_executable.is_file():
            raise ConfigurationError("指定的浏览器程序不存在。")
        return self

    def executable(self) -> str | None:
        explicit = (self.browser_executable or os.getenv("TREEHOUSE_BROWSER_EXECUTABLE")
                    or os.getenv("TREE_BROWSER_EXECUTABLE"))
        if explicit:
            return str(explicit)
        # Optional project-local test runtime; normal installs use Playwright's own runtime.
        matches = sorted((PROJECT_ROOT / ".runtime" / "browsers").glob(
            "chromium-*/chrome-win64/chrome.exe"
        ))
        return str(matches[-1]) if matches else None
