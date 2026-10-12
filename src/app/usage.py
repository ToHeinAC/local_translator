"""Usage log: one JSON object per line in ``<data_dir>/usage.jsonl`` (the only usage I/O).

``data/`` is gitignored, so the log stays on the server. Each line has ``ts`` (local time with
UTC offset), ``event`` and ``user``, plus event fields; see docs/architecture.md. It is meant
for later analysis, e.g. ``pandas.read_json(path, lines=True)``. No passwords, file names or
document text are logged.
"""

import json
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

FILE_NAME = "usage.jsonl"
_lock = threading.Lock()


def _local_now() -> datetime:
    return datetime.now().astimezone()


def log_event(
    data_dir: Path,
    event: str,
    user: str,
    *,
    now: Callable[[], datetime] = _local_now,
    **fields: Any,
) -> None:
    """Append one event; a write error is swallowed so logging never breaks the app."""
    record = {"ts": now().isoformat(timespec="seconds"), "event": event, "user": user, **fields}
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        with _lock, (data_dir / FILE_NAME).open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def read_events(data_dir: Path) -> list[dict[str, Any]]:
    """All logged events in order; empty if there is no log yet."""
    path = data_dir / FILE_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
