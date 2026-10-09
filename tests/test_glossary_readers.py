import io

import pytest
from openpyxl import Workbook

from app.glossary import GlossaryError
from app.readers import read_glossary_rows

EXPECTED = [["de", "en", "note"], ["Größe", "size", ""], ["Freigabe", "clearance", "a, b"]]
CSV = 'de,en,note\nGröße,size,\nFreigabe,clearance,"a, b"\n'
MD = "| de | en | note |\n|---|---|---|\n| Größe | size | |\n| Freigabe | clearance | a, b |\n"


def _xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in EXPECTED:
        ws.append([c or None for c in row])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("g.csv", CSV.encode()),
        ("g.csv", CSV.replace(",", ";").replace('"a; b"', '"a, b"').encode()),
        ("g.tsv", CSV.replace(",", "\t").replace('"a\t b"', "a, b").encode()),
        ("g.csv", b"\xef\xbb\xbf" + CSV.encode()),
        ("g.csv", CSV.encode("cp1252")),
        ("g.xlsx", _xlsx()),
        ("g.md", MD.encode()),
    ],
    ids=["comma", "semicolon", "tab", "bom", "cp1252", "xlsx", "md"],
)
def test_all_formats_yield_same_rows(name: str, data: bytes) -> None:
    assert read_glossary_rows(name, data) == EXPECTED


def test_md_without_table_raises() -> None:
    with pytest.raises(GlossaryError, match="Tabelle"):
        read_glossary_rows("g.md", b"just text")


def test_unsupported_extension_raises() -> None:
    with pytest.raises(GlossaryError, match="Dateityp"):
        read_glossary_rows("g.pdf", b"x")


def test_corrupt_xlsx_raises() -> None:
    with pytest.raises(GlossaryError, match="xlsx"):
        read_glossary_rows("g.xlsx", b"not a zip")
