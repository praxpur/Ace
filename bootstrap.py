"""Source-checkout bootstrap; installed package entry points do not need it."""
import json
import os
import sys
from pathlib import Path


def configure():
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    metadata = root / ".runtime" / "runtime.json"
    if metadata.is_file():
        try:
            data = json.loads(metadata.read_text(encoding="utf-8"))
            if data.get("python_version") == list(sys.version_info[:2]):
                sys.path.insert(0, str(root / ".runtime" / "python"))
                os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(root / ".runtime" / "browsers"))
        except (OSError, ValueError):
            pass
