from app.models import DEFAULT_TAG, MODELS, annotate, resolve_default


def test_registry_has_exactly_the_two_models_with_fast_default() -> None:
    assert [(m.key, m.tag) for m in MODELS] == [
        ("fast", "gemma4:e2b"),
        ("standard", "gemma4:e4b"),
    ]
    assert DEFAULT_TAG == "gemma4:e2b"


def test_resolve_default_accepts_registry_tags() -> None:
    assert resolve_default("gemma4:e4b") == ("gemma4:e4b", None)
    assert resolve_default(None) == (DEFAULT_TAG, None)
    assert resolve_default("") == (DEFAULT_TAG, None)


def test_invalid_default_falls_back_with_warning() -> None:
    tag, warning = resolve_default("llama3:8b")
    assert tag == DEFAULT_TAG
    assert warning is not None
    assert "llama3:8b" in warning


def test_annotate_marks_missing_models_with_pull_hint() -> None:
    statuses = annotate({"gemma4:e4b", "other:1b"})
    assert [s.installed for s in statuses] == [False, True]
    assert statuses[0].pull_hint == "ollama pull gemma4:e2b"
    assert statuses[1].pull_hint == ""


def test_annotate_ignores_tag_case() -> None:
    statuses = annotate({"GEMMA4:E2B", "Gemma4:E4b"})
    assert [s.installed for s in statuses] == [True, True]


def test_every_model_has_a_segment_size() -> None:
    assert all(500 <= m.segment_chars <= 6000 for m in MODELS)
