from app.glossary import Entry
from app.prompt import STRICT_MARKER, build_prompt

A = Entry("Freigabe", "clearance", "radiological", 2)
B = Entry("Haus", "house", "", 3)


def test_prompt_lists_only_given_entries_with_notes() -> None:
    prompt = build_prompt("[[1]] x", "de", "en", [A], None)
    assert '"Freigabe" -> "clearance" (note: radiological)' in prompt
    assert "Haus" not in prompt
    assert "German" in prompt
    assert "English" in prompt
    assert prompt.endswith("[[1]] x")


def test_prompt_without_entries_has_no_terminology_section() -> None:
    assert "terminology" not in build_prompt("[[1]] x", "de", "en", [], None).lower()


def test_prompt_context_and_strict_missed_terms() -> None:
    prompt = build_prompt(
        "[[1]] x", "de", "en", [A, B], ("Vorher", "Before"), strict=True, missed=[B]
    )
    assert "Vorher" in prompt
    assert "Before" in prompt
    assert STRICT_MARKER in prompt
    assert 'Missing: "house" for "Haus"' in prompt


def test_normal_prompt_has_no_strict_marker() -> None:
    assert STRICT_MARKER not in build_prompt("[[1]] x", "de", "en", [], None)


def test_strict_prompt_can_demand_a_full_translation() -> None:
    prompt = build_prompt("[[1]] x", "de", "en", [], None, strict=True, untranslated=True)
    assert "Translate every line completely into English" in prompt
    assert "Translate every line completely" not in build_prompt(
        "[[1]] x", "de", "en", [], None, strict=True
    )
