"""PDF (text layer) to Document adapter (pdfplumber). Headings are recovered from font size."""

import io
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass

import pdfplumber
from pdfplumber.pdf import PDF

from app.document import Block, Document, DocumentReadError, Kind, require_text

MAX_PDF_PAGES = 200
_ZONE = 0.1  # top/bottom fraction of a page where headers and footers live
_HEADING_RATIO = 1.15
_SENTENCE_END = (".", "!", "?", ":")


@dataclass(frozen=True)
class _Line:
    page: int
    text: str
    size: float
    top: float
    bottom: float


def read_pdf(data: bytes) -> Document:
    """Read a text-layer PDF into blocks; raises ``DocumentReadError`` for unusable files."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise DocumentReadError(f"PDF hat mehr als {MAX_PDF_PAGES} Seiten (Limit)")
            lines = _lines(pdf)
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError("Ungültige oder beschädigte PDF-Datei") from exc
    if not lines:
        raise DocumentReadError("Gescanntes PDF wird (noch) nicht unterstützt")
    return require_text(_blocks(lines))


def _lines(pdf: PDF) -> list[_Line]:
    lines: list[_Line] = []
    zone: dict[int, set[str]] = {}
    for number, page in enumerate(pdf.pages):
        for raw in page.extract_text_lines(return_chars=True):
            text = str(raw["text"]).strip()
            if not text:
                continue
            sizes = [float(c["size"]) for c in raw["chars"] if c["text"].strip()]
            line = _Line(number, text, round(statistics.median_high(sizes or [0]) * 2) / 2,
                         float(raw["top"]), float(raw["bottom"]))  # fmt: skip
            lines.append(line)
            if line.top < _ZONE * page.height or line.bottom > (1 - _ZONE) * page.height:
                zone.setdefault(number, set()).add(_signature(text))
    return _without_chrome(lines, zone, len(pdf.pages), pdf.pages[0].height if pdf.pages else 0)


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", text)


def _without_chrome(
    lines: list[_Line], zone: dict[int, set[str]], pages: int, height: float
) -> list[_Line]:
    counts = Counter(sig for sigs in zone.values() for sig in sigs)
    limit = max(2, math.ceil(0.6 * pages))
    repeated = {sig for sig, n in counts.items() if n >= limit}
    return [
        ln
        for ln in lines
        if not (
            _signature(ln.text) in repeated
            and (ln.top < _ZONE * height or ln.bottom > (1 - _ZONE) * height)
        )
    ]


def _blocks(lines: list[_Line]) -> Document:
    body = Counter[float]()
    for ln in lines:
        body[ln.size] += len(ln.text)
    body_size = body.most_common(1)[0][0] if body else 0.0
    sizes = sorted({ln.size for ln in lines if ln.size >= body_size * _HEADING_RATIO}, reverse=True)
    levels = {size: min(rank + 1, 6) for rank, size in enumerate(sizes)}
    blocks: Document = []
    prev: _Line | None = None
    for ln in lines:
        _add(blocks, prev, ln, levels.get(ln.size, 0), body_size)
        prev = ln
    return blocks


def _add(blocks: Document, prev: _Line | None, ln: _Line, level: int, body_size: float) -> None:
    last = blocks[-1] if blocks else None
    if level:
        merge = (
            last is not None and last.level == level and prev is not None
            and prev.page == ln.page and ln.top - prev.bottom <= 0.5 * ln.size
        )  # fmt: skip
        if merge and last is not None:
            blocks[-1] = Block(Kind.HEADING, _join(last.text, ln.text), level=level)
        else:
            blocks.append(Block(Kind.HEADING, ln.text, level=level))
    elif (
        last is not None and last.kind is Kind.PARAGRAPH and not _new_paragraph(prev, ln, body_size)
    ):
        blocks[-1] = Block(Kind.PARAGRAPH, _join(last.text, ln.text))
    else:
        blocks.append(Block(Kind.PARAGRAPH, ln.text))


def _new_paragraph(prev: _Line | None, ln: _Line, body_size: float) -> bool:
    if prev is None:
        return True
    if prev.page != ln.page:
        return prev.text.endswith(_SENTENCE_END)
    return ln.top - prev.bottom > 0.5 * body_size


def _join(first: str, second: str) -> str:
    if re.search(r"[^\W\d_]-$", first) and second[:1].islower():
        return first[:-1] + second
    return f"{first} {second}"
