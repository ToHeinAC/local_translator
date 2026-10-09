"""Model registry (pure). Same shape as the summarizer's; see PRD §5.3."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    key: str
    tag: str
    label: str  # German UI label
    speed: int  # 1-3 stars
    quality: int  # 1-3 stars


@dataclass(frozen=True)
class ModelStatus:
    info: ModelInfo
    installed: bool
    pull_hint: str  # "" if installed


MODELS = (
    ModelInfo("fast", "gemma4:e2b", "Schnell", 3, 1),
    ModelInfo("standard", "gemma4:e4b", "Standard", 2, 2),
    ModelInfo("precise", "qwen3:14b", "Präzise", 1, 3),
)
DEFAULT_TAG = "gemma4:e4b"


def resolve_default(value: str | None) -> tuple[str, str | None]:
    """The tag to preselect for ``DEFAULT_MODEL``; an unknown tag falls back with a warning."""
    if not value:
        return DEFAULT_TAG, None
    if value in {m.tag for m in MODELS}:
        return value, None
    return DEFAULT_TAG, f"DEFAULT_MODEL '{value}' ist nicht in der Registry; verwende {DEFAULT_TAG}"


def annotate(installed: set[str]) -> list[ModelStatus]:
    """Mark each registry model as installed or not, with the ``ollama pull`` hint."""
    return [
        ModelStatus(m, m.tag in installed, "" if m.tag in installed else f"ollama pull {m.tag}")
        for m in MODELS
    ]
