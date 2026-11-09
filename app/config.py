import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path):
    """Minimal .env reader: KEY=value lines; real environment variables win."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("\"'")
        if key.strip() and value:
            os.environ.setdefault(key.strip(), value)


_load_env(ROOT / ".env")
DATA = Path(os.environ.get("MOVIEMATCH_DATA", ROOT / "data" / "ml-latest-small"))
METRICS = DATA / "metrics.json"
STATIC = Path(__file__).resolve().parent / "static"

MIN_COUNT = 10
MIN_SIMILAR = 5
