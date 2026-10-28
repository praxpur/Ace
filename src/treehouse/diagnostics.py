import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4
from dataclasses import asdict


def safe_url(url: str) -> str:
    """Redact SSO tokens and nested redirects before recording a URL."""
    parsed = urlsplit(url)
    sensitive = re.compile(r"token|password|secret|cookie|ticket|code|auth|redirect|key|state", re.I)
    query = [
        (key, "[REDACTED]" if sensitive.search(key) else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query), ""))


def scrub_text(text: str) -> str:
    def scrub_url(match):
        try:
            return safe_url(match.group(0))
        except ValueError:
            return "[REDACTED URL]"
    text = re.sub(r"https?://[^\s'\"<>]+", scrub_url, text)
    return re.sub(
        r"(?i)\b(password|token|secret|cookie|ticket|auth_code)\s*[=:]\s*[^&\s,;]+",
        r"\1=[REDACTED]", text,
    )


class SafeFormatter(logging.Formatter):
    def format(self, record):
        return scrub_text(super().format(record))


class Diagnostics:
    def __init__(self, root: Path):
        self.path = root / f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
        self.path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(f"treehouse.{self.path.name}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.handler = logging.FileHandler(self.path / "run.log", encoding="utf-8")
        self.handler.setFormatter(SafeFormatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(self.handler)
        self._events = (self.path / "events.jsonl").open("a", encoding="utf-8")

    def event(self, kind: str, data: dict) -> None:
        self._events.write(json.dumps(
            {"time": datetime.now().isoformat(), "kind": kind, "data": data},
            ensure_ascii=False, allow_nan=False,
        ) + "\n")
        self._events.flush()

    def record_pages(self, context, adapter, error: Exception) -> None:
        pages = []
        for index, page in enumerate(context.pages if context else []):
            try:
                if page.is_closed():
                    continue
                probes = adapter.probe_page(page)
                pages.append({
                    "url": safe_url(page.url),
                    "title": page.title(),
                    "probes": [probe.serializable() for probe in probes],
                })
                masks = [frame.locator("input, textarea, [contenteditable='true']")
                         for frame in page.frames]
                page.screenshot(
                    path=str(self.path / f"page_{index}.png"), full_page=True, timeout=5000,
                    mask=masks, mask_color="#64748b",
                )
            except Exception as diagnostic_error:
                self.logger.warning("诊断页面 %s 失败：%s", index, diagnostic_error)
        (self.path / "failure.json").write_text(json.dumps(
            {"error_type": type(error).__name__, "message": scrub_text(str(error)), "pages": pages},
            ensure_ascii=False, indent=2, allow_nan=False,
        ), encoding="utf-8")

    def outcome(self, outcome):
        (self.path / "result.json").write_text(json.dumps(
            asdict(outcome), ensure_ascii=False, indent=2, allow_nan=False
        ), encoding="utf-8")

    def close(self) -> None:
        self._events.close()
        self.logger.removeHandler(self.handler)
        self.handler.close()
