"""Configuration from environment variables (pure: the mapping is passed in)."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.prompt import SUPPORTED_LANGUAGES

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Config:
    host: str
    default_model: str | None
    default_target: str
    segment_chars: int | None  # None: each model's own size (models.py)
    max_upload_mb: int
    timeout_s: float
    admins: tuple[str, ...]
    data_dir: Path


def _number(env: Mapping[str, str], key: str, default: float, kind: type) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = kind(raw)
    except ValueError:
        raise ValueError(f"{key} muss eine Zahl sein: '{raw}'") from None
    if value <= 0:
        raise ValueError(f"{key} muss größer als 0 sein: '{raw}'")
    return value


def load_config(env: Mapping[str, str]) -> Config:
    """Read the keys listed in ``.env.example``; invalid values raise ``ValueError``."""
    target = env.get("DEFAULT_TARGET_LANG", "").strip() or "en"
    if target not in SUPPORTED_LANGUAGES:
        raise ValueError(f"DEFAULT_TARGET_LANG '{target}' wird nicht unterstützt")
    raw_admins = env.get("ADMIN_USERS", "").strip() or "T. Hein"
    admins = tuple(a.strip() for a in raw_admins.split(",") if a.strip())
    return Config(
        host=env.get("OLLAMA_HOST", "").strip() or "http://localhost:11434",
        default_model=env.get("DEFAULT_MODEL", "").strip() or None,
        default_target=target,
        segment_chars=int(_number(env, "SEGMENT_CHARS", 0, int)) or None,
        max_upload_mb=int(_number(env, "MAX_UPLOAD_MB", 25, int)),
        timeout_s=float(_number(env, "LLM_TIMEOUT_S", 600.0, float)),
        admins=admins,
        data_dir=Path(env.get("DATA_DIR", "").strip() or DEFAULT_DATA_DIR),
    )
