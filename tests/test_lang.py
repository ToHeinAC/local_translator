from app.lang import is_in_language

EN = "The quick brown fox jumps over the lazy dog near the river bank."
DE = "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer."


def test_long_text_in_target_language_is_detected() -> None:
    assert is_in_language(EN, "en")
    assert not is_in_language(DE, "en")


def test_short_or_undetectable_text_never_counts() -> None:
    assert not is_in_language("The end", "en")
    assert not is_in_language("1234567890" * 6, "en")
