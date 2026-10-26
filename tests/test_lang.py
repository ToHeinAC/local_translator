from app.lang import is_in_language

EN = "The quick brown fox jumps over the lazy dog near the river bank."
DE = "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer."


def test_long_text_in_target_language_is_detected() -> None:
    assert is_in_language(EN, "en")
    assert not is_in_language(DE, "en")


def test_short_or_undetectable_text_never_counts() -> None:
    assert not is_in_language("The end", "en")
    assert not is_in_language("1234567890" * 6, "en")


def test_a_single_source_sentence_inside_a_translation_is_found() -> None:
    from app.lang import has_source_sentence

    assert has_source_sentence(f"{EN} {DE}", "de")
    assert has_source_sentence(f"<b>{EN}</b>\n{DE}", "de")
    assert not has_source_sentence(f"{EN} {EN}", "de")
    assert not has_source_sentence("Die Anlage. " + EN, "de")  # short sentences are not judged
