import json
from datetime import UTC, datetime
from pathlib import Path

from app.usage import FILE_NAME, log_event, read_events

NOW = datetime(2026, 10, 12, 9, 30, 5, tzinfo=UTC)


def test_events_are_appended_as_one_json_line_each(tmp_path: Path) -> None:
    log_event(tmp_path, "login_ok", "Jürgen", now=lambda: NOW, session="s1")
    log_event(tmp_path, "download", "Jürgen", now=lambda: NOW, format="pdf")
    lines = (tmp_path / FILE_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {
        "ts": "2026-10-12T09:30:05+00:00",
        "event": "login_ok",
        "user": "Jürgen",
        "session": "s1",
    }
    assert "Jürgen" in lines[1]  # readable, not \u-escaped
    assert [e["event"] for e in read_events(tmp_path)] == ["login_ok", "download"]


def test_a_missing_log_reads_as_empty(tmp_path: Path) -> None:
    assert read_events(tmp_path) == []


def test_a_write_error_never_reaches_the_caller(tmp_path: Path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    log_event(blocked, "login_ok", "x")  # must not raise
    assert blocked.read_text() == "not a directory"
