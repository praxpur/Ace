from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Phase(str, Enum):
    STARTING = "starting"
    WAITING_PAGE = "waiting_page"
    WAITING_LOGIN = "waiting_login"
    CHOOSING_COURSE = "choosing_course"
    LOADING_RESOURCES = "loading_resources"
    CHOOSING_VIDEO = "choosing_video"
    LOADING_VIDEO = "loading_video"
    PLAYING = "playing"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"


class PageKind(str, Enum):
    LOADING = "loading"
    LOGIN = "login"
    COURSES = "courses"
    RESOURCES = "resources"
    VIDEO = "video"
    COURSE_HOME = "course_home"
    EMPTY = "empty"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Event:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    status: str
    message: str
    diagnostic_dir: str

    @property
    def exit_code(self) -> int:
        return {"complete": 0, "cancelled": 2}.get(self.status, 1)
