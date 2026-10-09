import io
from collections.abc import Sequence

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.document import Block, Kind
from app.readers import DocumentReadError, read_document

HEIGHT = A4[1]


Item = tuple[str, float, float, bool]


def _pdf(pages: Sequence[Sequence[Item]], chrome: bool = True) -> bytes:
    """Each page: (text, y, size, bold) tuples; optional repeated header and footer."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for n, items in enumerate(pages, start=1):
        if chrome:
            c.setFont("Helvetica", 8)
            c.drawString(72, HEIGHT - 25, "Firma Intern - Vertraulich")
            c.drawString(72, 20, f"Seite {n}")
        for text, y, size, bold in items:
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(72, y, text)
        c.showPage()
    c.save()
    return buf.getvalue()


PAGES = [
    [
        ("Jahresbericht", 700, 20, True),
        ("Einleitung", 660, 14, True),
        ("Dies ist die Anlagen-", 630, 10, False),
        ("freigabe fuer alle.", 616, 10, False),
        ("Zweiter Absatz hier.", 588, 10, False),
    ],
    [("Ergebnisse", 700, 14, True), ("Alles gut verlaufen.", 670, 10, False)],
    [("Ende des Berichts.", 700, 10, False)],
]


def test_text_order_heading_levels_hyphens_and_repeated_chrome() -> None:
    blocks = read_document("b.pdf", _pdf(PAGES))
    assert [(b.kind, b.level, b.text) for b in blocks] == [
        (Kind.HEADING, 1, "Jahresbericht"),
        (Kind.HEADING, 2, "Einleitung"),
        (Kind.PARAGRAPH, 0, "Dies ist die Anlagenfreigabe fuer alle."),
        (Kind.PARAGRAPH, 0, "Zweiter Absatz hier."),
        (Kind.HEADING, 2, "Ergebnisse"),
        (Kind.PARAGRAPH, 0, "Alles gut verlaufen."),
        (Kind.PARAGRAPH, 0, "Ende des Berichts."),
    ]
    assert all("Seite" not in b.text and "Firma" not in b.text for b in blocks)


def test_paragraph_continues_across_page_without_final_punctuation() -> None:
    pages = [[("Ein Satz der", 700, 10, False)], [("weitergeht hier.", 700, 10, False)]]
    blocks = read_document("b.pdf", _pdf(pages, chrome=False))
    assert blocks == [Block(Kind.PARAGRAPH, "Ein Satz der weitergeht hier.")]


def test_pdf_without_text_layer_is_rejected() -> None:
    with pytest.raises(DocumentReadError, match="Gescanntes PDF"):
        read_document("b.pdf", _pdf([[]], chrome=False))


def test_corrupt_pdf_and_wrong_extension_give_clear_errors() -> None:
    with pytest.raises(DocumentReadError, match="PDF"):
        read_document("b.pdf", b"not a pdf")
    with pytest.raises(DocumentReadError, match="DOCX"):
        read_document("b.docx", _pdf(PAGES))


def test_pdf_over_page_limit_is_rejected_with_limit_in_message() -> None:
    pages = [[("Text", 700, 10, False)] for _ in range(201)]
    with pytest.raises(DocumentReadError, match="200"):
        read_document("b.pdf", _pdf(pages, chrome=False))
