import json
from pathlib import Path

import pytest

from app.auth import ensure_seeded, verify
from app.config import load_config


def test_config_defaults_and_overrides() -> None:
    cfg = load_config({})
    assert (cfg.host, cfg.default_target, cfg.segment_chars) == (
        "http://localhost:11434",
        "en",
        None,  # unset: each model's own segment size
    )
    assert (cfg.max_upload_mb, cfg.timeout_s, cfg.admins) == (25, 600.0, ("T. Hein",))
    cfg = load_config(
        {
            "OLLAMA_HOST": "http://h:1",
            "DEFAULT_TARGET_LANG": "fr",
            "SEGMENT_CHARS": "500",
            "MAX_UPLOAD_MB": "5",
            "LLM_TIMEOUT_S": "30",
            "ADMIN_USERS": "A, B C",
            "DEFAULT_MODEL": "qwen3:14b",
        }
    )
    assert (cfg.host, cfg.default_target, cfg.segment_chars) == ("http://h:1", "fr", 500)
    assert (cfg.max_upload_mb, cfg.timeout_s, cfg.admins) == (5, 30.0, ("A", "B C"))
    assert cfg.default_model == "qwen3:14b"


def test_empty_values_mean_defaults() -> None:
    env = {k: "" for k in ("ADMIN_USERS", "SEGMENT_CHARS", "OLLAMA_HOST", "DATA_DIR")}
    assert load_config(env) == load_config({})


def test_config_rejects_bad_numbers_and_languages() -> None:
    with pytest.raises(ValueError, match="SEGMENT_CHARS"):
        load_config({"SEGMENT_CHARS": "abc"})
    with pytest.raises(ValueError, match="DEFAULT_TARGET_LANG"):
        load_config({"DEFAULT_TARGET_LANG": "xx"})


def test_seeding_hashes_passwords_and_verify_checks_them(tmp_path: Path) -> None:
    env = {"SEED_PW_HEIN": "geheim", "SEED_PW_GAST": "gast"}
    ensure_seeded(tmp_path, env)
    stored = json.loads((tmp_path / "users.json").read_text())
    assert "geheim" not in json.dumps(stored)
    assert verify(tmp_path, "T. Hein", "geheim")
    assert verify(tmp_path, "Gast", "gast")
    assert not verify(tmp_path, "T. Hein", "falsch")
    assert not verify(tmp_path, "Unbekannt", "geheim")


def test_seeding_is_once_and_needs_passwords(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="SEED_PW_HEIN"):
        ensure_seeded(tmp_path, {})
    ensure_seeded(tmp_path, {"SEED_PW_HEIN": "a"})
    ensure_seeded(tmp_path, {"SEED_PW_HEIN": "b"})  # existing file is not touched
    assert verify(tmp_path, "T. Hein", "a")


def test_corrupt_user_file_denies_everyone(tmp_path: Path) -> None:
    (tmp_path / "users.json").write_text("{not json")
    assert not verify(tmp_path, "T. Hein", "x")
