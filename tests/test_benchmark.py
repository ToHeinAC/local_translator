from app.benchmark import TERMS, BenchResult, format_table, make_fixture, run_benchmark
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
    rows = [BenchResult("a", 61.0, 4, 10, 1, 0), BenchResult("b", 5.0, 4, 10, 0, 0)]
    table = format_table(rows)
    assert "| a | 61 s |" in table
    assert "90%" in table
    assert "100%" in table
