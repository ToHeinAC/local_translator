import re
from pathlib import Path

from app.benchmark import (
    TERMS,
    BenchResult,
    format_table,
    load_document,
    make_fixture,
    run_benchmark,
)
from app.document import Kind
from app.prompt import BODY_MARKER


def _translator(prompt: str) -> str:
    text = prompt.split(BODY_MARKER, 1)[1]
    for source, target in TERMS:
        text = text.replace(source, target)
    return text


def _echo(prompt: str) -> str:
    return prompt.split(BODY_MARKER, 1)[1]


def _clock() -> object:
    ticks = iter([10.0, 12.5])
    return lambda: next(ticks)


def test_fixture_has_headings_tables_and_glossary() -> None:
    doc, glossary = make_fixture(pages=3)
    kinds = [b.kind for b in doc]
    assert kinds.count(Kind.HEADING) == 3
    assert Kind.TABLE in kinds
    assert len(glossary.entries) == len(TERMS)
    assert sum(len(b.text) for b in doc) > 3 * 2000


def test_fixture_is_deterministic() -> None:
    assert make_fixture(pages=2)[0] == make_fixture(pages=2)[0]


def test_perfect_translator_has_full_hit_rate_and_timing() -> None:
    doc, glossary = make_fixture(pages=2)
    result = run_benchmark("m", _translator, doc, glossary, clock=_clock())  # type: ignore[arg-type]
    assert result.model == "m"
    assert result.seconds == 2.5
    assert result.hits > 0
    assert result.hit_rate == 1.0
    assert result.failed == 0
    assert result.segments >= 1


def test_echo_misses_every_term() -> None:
    doc, glossary = make_fixture(pages=2)
    result = run_benchmark("m", _echo, doc, glossary)
    assert result.hit_rate == 0.0


def test_format_table_lists_each_model() -> None:
    rows = [BenchResult("a", 61.0, 4, 10, 1, 0, 6, 2), BenchResult("b", 5.0, 4, 10, 0, 0, 4, 0)]
    table = format_table(rows)
    assert "| a | 61 s | 4 | 6 |" in table
    assert "| 2 |" in table
    assert "90%" in table
    assert "100%" in table


def _english(prompt: str) -> str:
    lines = re.findall(r"^\[\[(\d+)\]\]", prompt.split(BODY_MARKER, 1)[1], re.MULTILINE)
    return "\n".join(f"[[{n}]] The plant is inspected by the authority every year." for n in lines)


def test_untranslated_texts_and_calls_are_counted() -> None:
    doc, glossary = make_fixture(pages=1)
    echo = run_benchmark("m", _echo, doc, glossary)
    assert echo.untranslated > 0
    assert echo.calls > echo.segments  # echoes trigger retries
    english = run_benchmark("m", _english, doc, glossary)
    assert english.untranslated == 0


def test_document_benchmark_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("# Titel\n\n" + " ".join(["Die Anlage wird jedes Jahr geprüft."] * 5) + "\n")
    doc, glossary = load_document(str(path), "de", "en")
    assert len(doc) == 2
    assert (glossary.source_lang, glossary.target_lang, glossary.entries) == ("de", "en", ())
    result = run_benchmark("m", _english, doc, glossary, segment_chars=500)
    assert result.untranslated == 0


def test_document_benchmark_reads_a_glossary_file(tmp_path: Path) -> None:
    path, terms = tmp_path / "doc.md", tmp_path / "terms.csv"
    path.write_text("Die Freigabe wird von der Behörde geprüft und im Bericht dokumentiert.\n")
    terms.write_text("de,en\nFreigabe,clearance\nBehörde,authority\n")
    doc, glossary = load_document(str(path), "de", "en", str(terms))
    assert [(e.source, e.target) for e in glossary.entries] == [
        ("Freigabe", "clearance"),
        ("Behörde", "authority"),
    ]
    result = run_benchmark("m", _english, doc, glossary)
    assert result.hits == 2
    assert result.document[0].text == "The plant is inspected by the authority every year."
