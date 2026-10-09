import re

import pytest

from app.document import Block, Document, Kind, same_structure
from app.glossary import Glossary, build_glossary
from app.prompt import BODY_MARKER, STRICT_MARKER
from app.translate import FatalLlmError, translate_document

EMPTY = Glossary("de", "en", ())
DOC: Document = [
    Block(Kind.HEADING, "Titel der Anlage", level=1),
    Block(Kind.PARAGRAPH, "Siehe `code` und https://a.b/c bei 5 mm Dicke."),
    Block(Kind.LIST_ITEM, "Punkt eins"),
    Block(Kind.TABLE, rows=(("Name", "Wert"), ("Haus", "3"))),
    Block(Kind.CODE, "print('x')", info="py", translate=False),
]


class Fake:
    """Records prompts; ``handler`` maps a prompt to the model answer."""

    def __init__(self, handler=None) -> None:
        self.prompts: list[str] = []
        self.handler = handler or (lambda p: body(p).upper())

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.handler(prompt)


def body(prompt: str) -> str:
    return prompt.split(BODY_MARKER, 1)[1]


def _glossary(extra: list[list[str]] | None = None) -> Glossary:
    rows = [["de", "en", "note"], ["Freigabe", "clearance", "radiological"]] + (extra or [])
    return build_glossary(rows, "de", "en").glossary


def test_echo_keeps_structure_protected_spans_and_code() -> None:
    result = translate_document(DOC, EMPTY, Fake())
    out = result.document
    assert same_structure(DOC, out)
    assert out[0].text == "TITEL DER ANLAGE"
    assert out[1].text == "SIEHE `code` UND https://a.b/c BEI 5 mm DICKE."
    assert out[3].rows == (("NAME", "WERT"), ("HAUS", "3"))
    assert out[4] == DOC[4]
    assert result.failed == ()
    assert not result.cancelled


def test_nothing_translatable_makes_no_calls() -> None:
    fake = Fake()
    result = translate_document([DOC[4]], EMPTY, fake)
    assert fake.prompts == []
    assert result.document == [DOC[4]]


def test_prompt_contains_only_matched_entries() -> None:
    glossary = _glossary([["Haus", "house", ""]])
    fake = Fake()
    translate_document([Block(Kind.PARAGRAPH, "Die Freigabe erfolgt.")], glossary, fake)
    assert '"Freigabe" -> "clearance" (note: radiological)' in fake.prompts[0]
    assert "house" not in fake.prompts[0]


def test_term_drop_triggers_exactly_one_strict_retry() -> None:
    fake = Fake(lambda p: "[[1]] The clearance." if STRICT_MARKER in p else "[[1]] The approval.")
    result = translate_document([Block(Kind.PARAGRAPH, "Die Freigabe.")], _glossary(), fake)
    assert len(fake.prompts) == 2
    assert STRICT_MARKER in fake.prompts[1]
    assert 'Missing: "clearance" for "Freigabe"' in fake.prompts[1]
    assert result.document[0].text == "The clearance."
    assert (result.hits, result.enforced, result.misses) == (1, 1, [])


def test_persistent_term_miss_is_reported_not_blocking() -> None:
    fake = Fake(lambda _p: "[[1]] The approval.")
    result = translate_document([Block(Kind.PARAGRAPH, "Die Freigabe.")], _glossary(), fake)
    assert len(fake.prompts) == 2
    assert result.document[0].text == "The approval."
    (miss,) = result.misses
    assert (miss.block, miss.entry.target, miss.excerpt) == (0, "clearance", "Die Freigabe.")
    assert (result.hits, result.enforced) == (1, 0)


def _multi_only(drop):
    """Misbehave for prompts with two or more units, echo single-unit prompts."""

    def handler(prompt: str) -> str:
        text = body(prompt)
        return drop(text) if "[[2]]" in text else text.upper()

    return handler


def test_dropped_id_retries_then_falls_back_block_by_block() -> None:
    doc = [Block(Kind.PARAGRAPH, "Eins hier"), Block(Kind.PARAGRAPH, "Zwei hier")]
    fake = Fake(_multi_only(lambda t: t.split("\n")[0]))
    result = translate_document(doc, EMPTY, fake)
    assert len(fake.prompts) == 4
    assert STRICT_MARKER in fake.prompts[1]
    assert [b.text for b in result.document] == ["EINS HIER", "ZWEI HIER"]
    assert result.failed == ()


def test_dropped_token_retries_then_falls_back() -> None:
    doc = [Block(Kind.PARAGRAPH, "Eins `x`"), Block(Kind.PARAGRAPH, "Zwei")]
    fake = Fake(_multi_only(lambda t: t.replace("⟦P1⟧", "")))
    result = translate_document(doc, EMPTY, fake)
    assert len(fake.prompts) == 4
    assert [b.text for b in result.document] == ["EINS `x`", "ZWEI"]


def test_unit_failing_in_fallback_stays_source_and_is_marked() -> None:
    doc = [Block(Kind.PARAGRAPH, "Eins hier"), Block(Kind.PARAGRAPH, "Zwei hier")]

    def handler(prompt: str) -> str:
        text = body(prompt)
        return "garbage" if "Zwei" in text else text.upper()

    result = translate_document(doc, EMPTY, Fake(handler))
    assert [b.text for b in result.document] == ["EINS HIER", "Zwei hier"]
    assert result.failed == (1,)


@pytest.mark.parametrize("error", [RuntimeError("boom"), TimeoutError()])
def test_exception_leaves_segment_in_source_and_job_finishes(error: Exception) -> None:
    doc = [Block(Kind.PARAGRAPH, t) for t in ("Eins", "Zwei", "Drei")]

    def handler(prompt: str) -> str:
        if "Zwei" in body(prompt):
            raise error
        return body(prompt).upper()

    result = translate_document(doc, EMPTY, Fake(handler), segment_chars=5)
    assert [b.text for b in result.document] == ["EINS", "Zwei", "DREI"]
    assert result.failed == (1,)


def test_progress_is_monotonic_and_ends_complete() -> None:
    doc = [Block(Kind.PARAGRAPH, t) for t in ("Eins", "Zwei", "Drei")]
    seen: list[tuple[int, int]] = []
    translate_document(
        doc, EMPTY, Fake(), progress=lambda d, t: seen.append((d, t)), segment_chars=5
    )
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_cancel_stops_after_current_segment() -> None:
    doc = [Block(Kind.PARAGRAPH, t) for t in ("Eins", "Zwei", "Drei")]
    fake = Fake()
    result = translate_document(
        doc, EMPTY, fake, cancel=lambda: len(fake.prompts) >= 1, segment_chars=5
    )
    assert result.cancelled
    assert [b.text for b in result.document] == ["EINS", "Zwei", "Drei"]
    assert len(fake.prompts) == 1


def test_cancel_after_last_segment_is_not_cancelled() -> None:
    result = translate_document(DOC[:1], EMPTY, Fake(), cancel=lambda: True)
    assert not result.cancelled


def test_long_block_is_split_at_sentences_and_rejoined() -> None:
    doc = [Block(Kind.PARAGRAPH, "Erster Satz. Zweiter Satz. Dritter Satz.")]
    fake = Fake()
    result = translate_document(doc, EMPTY, fake, segment_chars=20)
    assert len(fake.prompts) == 3
    assert result.document[0].text == "ERSTER SATZ. ZWEITER SATZ. DRITTER SATZ."


def test_preamble_and_think_tags_are_stripped() -> None:
    fake = Fake(lambda _p: "<think>x</think>\nHere is the translation:\n[[1]] Hallo")
    result = translate_document([Block(Kind.PARAGRAPH, "Hello")], EMPTY, fake)
    assert result.document[0].text == "Hallo"


def test_previous_segment_is_passed_as_context() -> None:
    doc = [Block(Kind.PARAGRAPH, "Eins"), Block(Kind.PARAGRAPH, "Zwei")]
    fake = Fake()
    translate_document(doc, EMPTY, fake, segment_chars=5)
    assert "Source: Eins\nTranslation: EINS" in fake.prompts[1]
    assert "Context" not in fake.prompts[0]


def test_fatal_llm_error_aborts_the_job() -> None:
    def handler(_prompt: str) -> str:
        raise FatalLlmError("host down")

    with pytest.raises(FatalLlmError):
        translate_document(DOC[:1], EMPTY, Fake(handler))


GERMAN_LINE = "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer."


def test_echoed_line_is_retried_with_a_translate_everything_instruction() -> None:
    def handler(prompt: str) -> str:
        return body(prompt) if STRICT_MARKER not in prompt else body(prompt).upper()

    fake = Fake(handler)
    result = translate_document([Block(Kind.PARAGRAPH, GERMAN_LINE)], EMPTY, fake)
    assert result.document[0].text == GERMAN_LINE.upper()
    assert result.failed == ()
    assert len(fake.prompts) == 2
    assert "Translate every line completely into English" in fake.prompts[1]


def test_line_that_stays_identical_after_the_retry_is_reported_as_failed() -> None:
    fake = Fake(lambda prompt: body(prompt))
    result = translate_document([Block(Kind.PARAGRAPH, GERMAN_LINE)], EMPTY, fake)
    assert result.failed == (0,)
    assert result.document[0].text == GERMAN_LINE


def test_short_unchanged_text_is_not_treated_as_an_echo() -> None:
    fake = Fake(lambda prompt: body(prompt))
    result = translate_document([Block(Kind.PARAGRAPH, "Siehe Anlage 3")], EMPTY, fake)
    assert result.failed == ()
    assert len(fake.prompts) == 1


ECHO_DE = "Der schnelle braune Fuchs springt über den faulen Hund am Flussufer."
NEXT_DE = "Die Anlage wird nach der Prüfung durch den Sachverständigen freigegeben."
NEXT_EN = "The plant is released after the inspection by the expert."


def test_an_echoed_answer_is_never_passed_on_as_context() -> None:
    def handler(prompt: str) -> str:
        return body(prompt) if ECHO_DE in body(prompt) else f"[[1]] {NEXT_EN}"

    fake = Fake(handler)
    doc = [Block(Kind.PARAGRAPH, ECHO_DE), Block(Kind.PARAGRAPH, NEXT_DE)]
    translate_document(doc, EMPTY, fake, segment_chars=80)
    later = [p for p in fake.prompts if NEXT_DE in body(p)]
    assert later
    assert all("Translation: Der schnelle" not in p for p in later)


def test_good_context_survives_an_echoed_segment() -> None:
    first = "Die Pumpe wurde im letzten Jahr vollständig überholt und geprüft."
    answers = {first: "[[1]] The pump was fully overhauled and tested last year."}

    def handler(prompt: str) -> str:
        text = body(prompt)
        for source, answer in answers.items():
            if source in text:
                return answer
        return text if ECHO_DE in text else f"[[1]] {NEXT_EN}"

    fake = Fake(handler)
    doc = [Block(Kind.PARAGRAPH, t) for t in (first, ECHO_DE, NEXT_DE)]
    translate_document(doc, EMPTY, fake, segment_chars=80)
    last = next(p for p in fake.prompts if NEXT_DE in body(p))
    assert "Translation: The pump was fully overhauled" in last


def test_short_lines_echoed_together_trigger_the_retry() -> None:
    lines = ["Die Anlage wird geprüft", "Der Bericht ist fertig", "Die Freigabe fehlt noch"]
    fake = Fake(lambda prompt: body(prompt))
    translate_document([Block(Kind.LIST_ITEM, t) for t in lines], EMPTY, fake)
    assert len(fake.prompts) >= 2
    assert "Translate every line completely into English" in fake.prompts[1]


def test_echoed_segment_ending_in_a_short_heading_is_not_used_as_context() -> None:
    doc = [
        Block(Kind.PARAGRAPH, ECHO_DE),
        Block(Kind.HEADING, "Ergebnisse", level=2),
        Block(Kind.PARAGRAPH, NEXT_DE),
    ]

    def handler(prompt: str) -> str:
        text = body(prompt)
        return f"[[1]] {NEXT_EN}" if NEXT_DE in text else text

    fake = Fake(handler)
    translate_document(doc, EMPTY, fake, segment_chars=100)
    last = next(p for p in fake.prompts if NEXT_DE in body(p))
    assert "Context" not in last


def test_unchanged_proper_names_are_not_reported_as_failed() -> None:
    names = "The Clearing House (JPMorgan, Citi, Bank of America, Wells Fargo)"
    fake = Fake(lambda prompt: body(prompt))
    glossary = Glossary("en", "de", ())
    result = translate_document([Block(Kind.PARAGRAPH, names)], glossary, fake)
    assert result.failed == ()
    assert result.document[0].text == names


def _english_lines(prompt: str) -> str:
    ids = re.findall(r"^\[\[(\d+)\]\]", body(prompt), re.MULTILINE)
    return "\n".join(f"[[{n}]] This is the translated line." for n in ids)


def test_broken_segment_is_halved_before_single_lines() -> None:
    def handler(prompt: str) -> str:
        lines = re.findall(r"^\[\[\d+\]\]", body(prompt), re.MULTILINE)
        return "garbage" if len(lines) > 2 else _english_lines(prompt)

    fake = Fake(handler)
    doc = [Block(Kind.PARAGRAPH, f"Absatz Nummer {i}") for i in range(4)]
    result = translate_document(doc, EMPTY, fake)
    assert result.failed == ()
    assert len(fake.prompts) == 4  # full segment + strict retry, then two halves
    assert all(b.text == "This is the translated line." for b in result.document)


def test_halving_goes_down_to_single_lines_when_needed() -> None:
    def handler(prompt: str) -> str:
        lines = re.findall(r"^\[\[\d+\]\]", body(prompt), re.MULTILINE)
        return "garbage" if len(lines) > 1 else _english_lines(prompt)

    fake = Fake(handler)
    doc = [Block(Kind.PARAGRAPH, f"Absatz Nummer {i}") for i in range(3)]
    result = translate_document(doc, EMPTY, fake)
    assert result.failed == ()
    assert all(b.text == "This is the translated line." for b in result.document)


def test_paragraphs_already_in_the_target_language_are_not_sent() -> None:
    english = "The quick brown fox jumps over the lazy dog near the river bank."
    fake = Fake(_english_lines)
    doc = [Block(Kind.PARAGRAPH, english), Block(Kind.PARAGRAPH, ECHO_DE)]
    result = translate_document(doc, EMPTY, fake)
    assert english not in "".join(fake.prompts)
    assert result.document[0].text == english
    assert result.document[1].text == "This is the translated line."
