import pytest

from app.glossary import (
    GLOSSARY_TEMPLATE_CSV,
    Glossary,
    GlossaryError,
    build_glossary,
)
from app.readers import read_glossary_rows

ROWS = [
    ["de", "en", "fr", "note"],
    ["Abklingbecken", "spent fuel pool", "piscine", ""],
    ["Freigabe", "clearance", "libération", "radiological meaning"],
    ["Freigabeverfahren", "clearance procedure", "", ""],
]


def _glossary(rows: list[list[str]] = ROWS, src: str = "de", tgt: str = "en") -> Glossary:
    return build_glossary(rows, src, tgt).glossary


def test_entries_filtered_for_pair_with_note_and_row_number() -> None:
    result = build_glossary(ROWS, "de", "fr")
    assert [(e.source, e.target, e.row) for e in result.glossary.entries] == [
        ("Abklingbecken", "piscine", 2),
        ("Freigabe", "libération", 3),
    ]
    assert result.glossary.entries[1].note == "radiological meaning"
    assert [(i.row, i.kind) for i in result.issues] == [(4, "empty_cell")]


def test_header_codes_case_insensitive() -> None:
    assert len(_glossary([["DE", "En"], ["Haus", "house"]]).entries) == 1


def test_missing_language_names_available_ones() -> None:
    with pytest.raises(GlossaryError, match=r"'pl'.*de, en, fr"):
        build_glossary(ROWS, "de", "pl")


def test_duplicate_and_conflict_rows_reported() -> None:
    rows = [
        ["de", "en"],
        ["Haus", "house"],
        ["haus", "house"],
        ["Tür", "door"],
        ["Tür", "gate"],
        ["", ""],
        ["Dach", "roof"],
    ]
    result = build_glossary(rows, "de", "en")
    assert [e.source for e in result.glossary.entries] == ["Haus", "Dach"]
    assert [(i.row, i.kind) for i in result.issues] == [
        (3, "duplicate"),
        (4, "conflict"),
        (5, "conflict"),
    ]


def test_identical_source_and_target_means_keep_as_is() -> None:
    assert len(_glossary([["de", "en"], ["Kerma", "Kerma"]]).entries) == 1


def test_empty_glossary_has_no_entries_and_no_error() -> None:
    result = build_glossary([["de", "en"]], "de", "en")
    assert result.glossary.entries == ()


def test_large_glossary_only_matched_entries_returned() -> None:
    rows = [["de", "en"], *[[f"Begriff{i}x", f"term{i}"] for i in range(6000)]]
    glossary = _glossary(rows)
    assert len(glossary.entries) == 6000
    assert [m.entry.target for m in glossary.match("Der Begriff42x gilt.")] == ["term42"]


@pytest.mark.parametrize(
    ("text", "hits"),
    [
        ("Die Freigabe erfolgt.", 1),
        ("Zwei Freigaben liegen vor.", 1),
        ("Die Anlagenfreigabe erfolgt.", 1),
        ("Er will freigeben.", 0),
        ("Freigabe und freigabe", 2),
    ],
)
def test_match_inflection_compound_and_negative(text: str, hits: int) -> None:
    matches = _glossary().match(text)
    assert sum(m.count for m in matches) == hits


def test_longest_match_wins() -> None:
    (m,) = _glossary().match("Das Freigabeverfahren läuft.")
    assert m.entry.source == "Freigabeverfahren"
    rows = [["de", "en"], ["Brennstab", "fuel rod"], ["Brennstabbündel", "fuel assembly"]]
    (m,) = _glossary(rows).match("Das Brennstabbündel")
    assert m.entry.target == "fuel assembly"


def test_compound_matching_is_german_only() -> None:
    rows = [["en", "de"], ["pool", "Becken"]]
    assert _glossary(rows, "en", "de").match("a carpool") == []
    assert len(_glossary(rows, "en", "de").match("a pool")) == 1


def test_verify_requires_target_at_least_as_often_as_source() -> None:
    glossary = _glossary()
    matches = glossary.match("Freigabe, Freigabe und Abklingbecken.")
    assert glossary.verify("Clearance, clearance and spent fuel pool.", matches) == []
    misses = glossary.verify("Clearance and spent fuel pool.", matches)
    assert [e.source for e in misses] == ["Freigabe"]
    misses = glossary.verify("Approval and the pool.", matches)
    assert [e.source for e in misses] == ["Abklingbecken", "Freigabe"]


def test_verify_tolerates_target_inflection() -> None:
    glossary = _glossary()
    matches = glossary.match("Freigabe")
    assert glossary.verify("Several clearances.", matches) == []


def test_template_is_valid_input() -> None:
    rows = read_glossary_rows("glossar_vorlage.csv", GLOSSARY_TEMPLATE_CSV.encode())
    result = build_glossary(rows, "de", "en")
    assert result.glossary.entries
    assert result.issues == []
