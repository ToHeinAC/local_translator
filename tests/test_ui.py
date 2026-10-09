import ast
import os
import re
import signal
import threading
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from app import llm_ollama, theme
from app.i18n import LANGUAGE_NAMES, STRINGS
from app.prompt import BODY_MARKER, SUPPORTED_LANGUAGES

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "app" / "ui.py"
ENV_KEYS = [
    "OLLAMA_HOST", "DEFAULT_MODEL", "DEFAULT_TARGET_LANG", "SEGMENT_CHARS", "MAX_UPLOAD_MB",
    "LLM_TIMEOUT_S", "SEED_PW_HEIN", "SEED_PW_GAST", "ADMIN_USERS", "DATA_DIR",
]  # fmt: skip
GERMAN = "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer."
GLOSSARY = b"de,en\nFuchs,vixen\n"


def upper(prompt: str) -> str:
    return prompt.split(BODY_MARKER, 1)[1].upper()


class Env:
    """Patches the Ollama adapter and builds ``AppTest`` instances for the UI script."""

    def __init__(self, mp: pytest.MonkeyPatch, tmp: Path) -> None:
        self.llm: Callable[[str], str] = upper
        self.installed = {"gemma4:e4b"}
        self.mp = mp
        for key in ENV_KEYS:
            mp.setenv(key, "")
        mp.setenv("DATA_DIR", str(tmp))
        client = SimpleNamespace(ps=lambda: SimpleNamespace(models=[]))
        mp.setattr(llm_ollama, "make_client", lambda _h, _t: client)
        mp.setattr(llm_ollama, "installed_tags", lambda _c, _h: self.installed)
        mp.setattr(llm_ollama, "make_llm", lambda _c, _m, _h: lambda p: self.llm(p))

    def app(self, user: str | None = "T. Hein") -> AppTest:
        at = AppTest.from_file(str(UI), default_timeout=30)
        if user:
            at.session_state["user"] = user
        return at.run()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Env:
    return Env(monkeypatch, tmp_path)


def _upload(at: AppTest, name: str = "bericht.md", data: bytes = GERMAN.encode()) -> AppTest:
    at.file_uploader[0].upload(name, data)
    return at.run()


def _translate(at: AppTest) -> AppTest:
    at.button(key="start_btn").click()
    at.run()
    handle = at.session_state.get("job")
    if handle is not None:
        handle.join(30)
    return at.run()


def test_streamlit_config_matches_the_prd() -> None:
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert cfg["server"]["port"] == 8560
    assert cfg["server"]["baseUrlPath"] == "trns"
    assert cfg["server"]["enableXsrfProtection"] is True
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["theme"]["primaryColor"] == theme.FOREST["primary"]
    assert cfg["theme"]["backgroundColor"] == theme.FOREST["bg"]
    assert cfg["theme"]["secondaryBackgroundColor"] == theme.FOREST["sidebar_bg"]


def test_every_string_exists_in_both_languages_with_the_same_placeholders() -> None:
    field = re.compile(r"\{(\w+)\}")
    for key, entry in STRINGS.items():
        assert set(entry) == {"de", "en"}, key
        assert field.findall(entry["de"]) == field.findall(entry["en"]), key
        assert all(entry.values()), key
    assert set(LANGUAGE_NAMES) == set(SUPPORTED_LANGUAGES)


def test_ui_only_uses_defined_string_keys() -> None:
    tree = ast.parse(UI.read_text())
    used: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", "")
        if name == "_language_select":  # passes string keys on to t()
            used.update(str(a.value) for a in node.args[1:3] if isinstance(a, ast.Constant))
        elif name == "t" and node.args and isinstance(node.args[0], ast.Constant):
            used.add(str(node.args[0].value))
        elif name == "t" and node.args and isinstance(node.args[0], ast.JoinedStr):
            prefix = str(node.args[0].values[0].value)  # type: ignore[attr-defined]
            assert any(k.startswith(prefix) for k in STRINGS), prefix
    assert used <= set(STRINGS), used - set(STRINGS)
    for ext in ("md", "docx", "pdf"):
        assert f"download_{ext}" in STRINGS
    for kind in ("empty_cell", "duplicate", "conflict"):
        assert f"issue_{kind}" in STRINGS
    for feature in ("footnotes", "endnotes", "comments", "text boxes"):
        assert f"feature_{feature}" in STRINGS


def test_end_to_end_flow_with_glossary_and_term_report(env: Env) -> None:
    at = _upload(env.app())
    at.file_uploader[1].upload("g.csv", GLOSSARY)
    at.run()
    assert any("1" in m.value and "Einträge" in m.value for m in at.markdown)
    at = _translate(at)
    assert not at.exception
    for ext in ("md", "docx", "pdf"):
        assert at.download_button(key=f"dl_{ext}") is not None
    assert [e.label for e in at.expander if e.label == "Terminologiebericht"]
    assert any("DER SCHNELLE BRAUNE FUCHS" in m.value for m in at.markdown)
    assert any("Fuchs" in str(row) for df in at.dataframe for row in df.value.values.tolist())
    assert at.download_button(key="dl_report") is not None


def test_results_survive_a_rerun_and_a_new_upload_clears_them(env: Env) -> None:
    at = _translate(_upload(env.app()))
    assert "result" in at.session_state
    at.run()
    assert "result" in at.session_state
    at.file_uploader[0].upload("anderes.md", b"# Andere Datei\n")
    at.run()
    assert "result" not in at.session_state


def test_same_source_and_target_language_is_blocked(env: Env) -> None:
    at = _upload(env.app())
    at.selectbox(key="target").set_value("de")
    at.run()
    assert at.button(key="start_btn").disabled
    assert any("verschieden" in e.value for e in at.error)


def test_missing_model_shows_the_pull_hint_and_blocks_start(env: Env) -> None:
    env.installed = set()
    at = _upload(env.app())
    assert any("ollama pull gemma4:e4b" in w.value for w in at.warning)
    assert at.button(key="start_btn").disabled


def test_oversized_and_unreadable_uploads_give_messages(env: Env, monkeypatch: Any) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    at = _upload(env.app(), data=b"x" * (2 * 1024 * 1024))
    assert any("größer als 1 MB" in e.value for e in at.error)
    at = _upload(env.app(), "kaputt.docx", b"kein zip")
    assert any("Datei nicht lesbar" in e.value for e in at.error)


def test_double_click_starts_only_one_job(env: Env) -> None:
    gate = threading.Event()
    calls: list[str] = []

    def slow(prompt: str) -> str:
        calls.append(prompt)
        gate.wait(10)
        return "[[1]] The quick brown fox jumps over the lazy dog near the river."

    env.llm = slow
    at = _upload(env.app())
    at.button(key="start_btn").click()
    at.run()
    assert at.button(key="start_btn").disabled
    handle = at.session_state["job"]
    gate.set()
    handle.join(30)
    at.run()
    assert len(calls) == 1


def test_cancel_button_requests_cancellation(env: Env) -> None:
    gate = threading.Event()
    env.llm = lambda p: (gate.wait(10), upper(p))[1]
    at = _upload(env.app())
    at.button(key="start_btn").click()
    at.run()
    handle = at.session_state["job"]
    at.button(key="cancel_btn").click()
    at.run()
    assert handle.cancel_requested
    gate.set()
    handle.join(30)


def test_failed_job_shows_the_error(env: Env) -> None:
    def broken(_prompt: str) -> str:
        raise llm_ollama.OllamaUnavailableError("http://x")

    env.llm = broken
    at = _translate(_upload(env.app()))
    assert any("nicht erreichbar" in e.value for e in at.error)


def test_exit_button_is_admin_only_and_asks_for_confirmation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))
    assert "exit_btn" not in [b.key for b in env.app("Gast").sidebar.button]
    at = env.app("T. Hein")
    at.sidebar.button(key="exit_btn").click()
    at.run()
    assert sent == []
    at.sidebar.button(key="exit_no_btn").click()
    at.run()
    assert "exit_yes_btn" not in [b.key for b in at.sidebar.button]
    at.sidebar.button(key="exit_btn").click()
    at.run()
    at.sidebar.button(key="exit_yes_btn").click()
    at.run()
    assert sent == [(os.getpid(), signal.SIGTERM)]


def test_login_language_toggle_and_logout(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_PW_HEIN", "geheim")
    at = env.app(user=None)
    assert not at.sidebar.button
    at.text_input[0].input("T. Hein")
    at.text_input[1].input("falsch")
    at.button[0].click()
    at.run()
    assert any("ungültig" in e.value for e in at.error)
    at.text_input[1].input("geheim")
    at.button[0].click()
    at.run()
    assert at.session_state["user"] == "T. Hein"
    at.sidebar.button(key="lang_btn").click()
    at.run()
    assert at.title[0].value == "AI Translator"
    at.sidebar.button(key="logout_btn").click()
    at.run()
    assert "user" not in at.session_state
    assert at.session_state["ui_lang"] == "en"


def test_missing_seed_passwords_and_bad_config_show_messages(env: Env) -> None:
    assert any("Start-Passwörter" in e.value for e in env.app(user=None).error)
    os.environ["SEGMENT_CHARS"] = "abc"
    assert any("SEGMENT_CHARS" in e.value for e in env.app().error)


def test_dollar_signs_in_the_preview_are_not_rendered_as_math(env: Env) -> None:
    env.llm = lambda p: body_text(p)
    at = _upload(env.app(), "geld.md", b"Cost 700 $ and 900 $ today.\n")
    at.selectbox(key="target").set_value("de")
    at = _translate(at.run())
    assert any(r"700 \$ and 900 \$" in m.value for m in at.markdown)


def body_text(prompt: str) -> str:
    return prompt.split(BODY_MARKER, 1)[1]
