"""Document to PDF bytes (reportlab, bundled DejaVu fonts for full Latin Extended coverage)."""

# reportlab's font registry is untyped.
# pyright: reportUnknownMemberType=false

import io
from collections.abc import Iterator
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.document import Block, Document, Kind
from app.inline import Run, parse_inline

WIDE_TABLE_COLUMNS = 8
_FONTS = Path(__file__).parent / "fonts"
_SANS, _BOLD, _ITALIC, _BOLD_ITALIC, _MONO = (
    "DejaVuSans",
    "DejaVuSans-Bold",
    "DejaVuSans-Oblique",
    "DejaVuSans-BoldOblique",
    "DejaVuSansMono",
)
_HEADING_SIZE = {1: 20, 2: 16, 3: 14, 4: 12, 5: 11, 6: 10}
_INDENT = 18


def write_pdf(doc: Document, *, title: str, author: str) -> bytes:
    """Render ``doc`` as an A4 PDF; landscape if any table has more than 8 columns."""
    _register_fonts()
    wide = any(b.kind is Kind.TABLE and len(b.rows[0]) > WIDE_TABLE_COLUMNS for b in doc)
    buf = io.BytesIO()
    page = landscape(A4) if wide else A4
    SimpleDocTemplate(buf, pagesize=page, title=title, author=author).build(
        list(_flowables(doc, wide))
    )
    return buf.getvalue()


def _register_fonts() -> None:
    if _SANS in pdfmetrics.getRegisteredFontNames():
        return
    for name in (_SANS, _BOLD, _ITALIC, _BOLD_ITALIC, _MONO):
        pdfmetrics.registerFont(TTFont(name, str(_FONTS / f"{name}.ttf")))
    pdfmetrics.registerFontFamily(
        _SANS, normal=_SANS, bold=_BOLD, italic=_ITALIC, boldItalic=_BOLD_ITALIC
    )


def _markup(text: str) -> str:
    return "".join(_run_markup(r) for r in parse_inline(text))


def _run_markup(run: Run) -> str:
    out = escape(run.text).replace("\n", "<br/>")
    if run.code:
        out = f'<font face="{_MONO}">{out}</font>'
    if run.bold:
        out = f"<b>{out}</b>"
    if run.italic:
        out = f"<i>{out}</i>"
    if run.href:
        out = f'<a href="{escape(run.href, {chr(34): "&quot;"})}" color="#0563C1">{out}</a>'
    return out


def _flowables(doc: Document, wide: bool) -> Iterator[Flowable]:
    counters: dict[int, int] = {}
    for block in doc:
        if block.kind is not Kind.LIST_ITEM:
            counters.clear()
        yield from _flowable(block, counters, wide)


def _flowable(block: Block, counters: dict[int, int], wide: bool) -> Iterator[Flowable]:
    match block.kind:
        case Kind.HEADING:
            size = _HEADING_SIZE.get(block.level, 10)
            style = ParagraphStyle(
                f"h{block.level}",
                fontName=_BOLD,
                fontSize=size,
                leading=size * 1.25,
                spaceBefore=size * 0.8,
                spaceAfter=size * 0.4,
                keepWithNext=1,
            )
            yield Paragraph(_markup(block.text), style)
        case Kind.LIST_ITEM:
            yield _list_item(block, counters)
        case Kind.TABLE:
            yield _table(block, wide)
            yield Spacer(1, 8)
        case Kind.CODE:
            style = ParagraphStyle("code", fontName=_MONO, fontSize=8, leading=10)
            yield Preformatted(block.text, style)
        case Kind.PAGE_BREAK:
            yield PageBreak()
        case Kind.QUOTE:
            style = ParagraphStyle("quote", fontName=_ITALIC, leftIndent=_INDENT, spaceAfter=6)
            yield Paragraph(_markup(block.text), style)
        case _:
            yield Paragraph(_markup(block.text), _body())


def _body() -> ParagraphStyle:
    return ParagraphStyle("body", fontName=_SANS, fontSize=10, leading=13, spaceAfter=6)


def _list_item(block: Block, counters: dict[int, int]) -> Paragraph:
    for deeper in [k for k in counters if k > block.depth]:
        del counters[deeper]
    if block.ordered:
        counters[block.depth] = counters.get(block.depth, 0) + 1
        bullet = f"{counters[block.depth]}."
    else:
        counters.pop(block.depth, None)
        bullet = "•"
    indent = _INDENT * (block.depth + 1)
    style = ParagraphStyle(
        "li",
        parent=_body(),
        leftIndent=indent,
        bulletIndent=indent - _INDENT,
        bulletFontName=_SANS,
        spaceAfter=2,
    )
    return Paragraph(_markup(block.text), style, bulletText=bullet)


def _table(block: Block, wide: bool) -> Table:
    size = 7 if wide else 9
    cell = ParagraphStyle("cell", fontName=_SANS, fontSize=size, leading=size * 1.25)
    head = ParagraphStyle("head", parent=cell, fontName=_BOLD)
    data = [
        [Paragraph(_markup(text), head if i == 0 else cell) for text in row]
        for i, row in enumerate(block.rows)
    ]
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table
