"""Segmenting, protected spans and the numbered-line wire format (pure)."""

import re
from dataclasses import dataclass

from app.document import Block, Document, Kind
from app.lang import is_in_language
from app.run_tags import strip_tags

Cell = tuple[int, int]

_UNITS = ["mm", "cm", "km", "m", "kg", "mg", "µg", "g", "ml", "l", "%", "°C", "°", "Bq", "kBq",
          "MBq", "Sv", "mSv", "µSv", "Gy", "mGy", "kW", "MW", "W", "kV", "V", "mA", "A", "Hz",
          "kHz", "MHz", "h", "min", "s"]  # fmt: skip
_UNIT_RE = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
_PROTECT = re.compile(
    "|".join(
        [
            r"`[^`\n]+`",
            r"\[\^[^\]\s]+\]",  # Markdown footnote reference
            r"https?://[^\s)>\]]*[^\s)>\].,;:!?]",
            r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
            r"\{[^{}\s]*\}",
            rf"\d+(?:[.,]\d+)?\s?(?:{_UNIT_RE})(?![A-Za-zµ])",
        ]
    )
)
_TOKEN = re.compile(r"⟦P\d+⟧")
_MARKER = re.compile(r"^\[\[(\d+)\]\]\s?(.*)$")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Unit:
    """One piece of text sent to the model: a block, a table cell, or a sentence group."""

    idx: int  # global position in the unit list
    block: int
    cell: Cell | None
    piece: int  # >0 if a long text was split
    text: str


@dataclass(frozen=True)
class Encoded:
    body: str
    spans: list[dict[str, str]]  # protected token -> original text, per unit
    units: list[Unit]


def split_sentences(text: str, limit: int) -> list[str]:
    """Pack sentences into pieces of at most ``limit`` characters (a sentence is never cut)."""
    pieces: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        if pieces and len(pieces[-1]) + 1 + len(sentence) <= limit:
            pieces[-1] += " " + sentence
        else:
            pieces.append(sentence)
    return pieces


def _texts(block: Block) -> list[tuple[Cell | None, str]]:
    if block.kind is Kind.TABLE:
        return [((r, c), text) for r, row in enumerate(block.rows) for c, text in enumerate(row)]
    return [(None, block.text)]


def plan_units(doc: Document, limit: int, target_lang: str = "") -> list[Unit]:
    """Flatten translatable text into units in document order; long text is split.

    Text without letters, and text of 40+ characters already in ``target_lang`` (FR-6a), is left
    out, so it is copied unchanged.
    """
    units: list[Unit] = []
    for bi, block in enumerate(doc):
        if not block.translate:
            continue
        for cell, text in _texts(block):
            if not any(ch.isalpha() for ch in text):
                continue
            if target_lang and is_in_language(strip_tags(text), target_lang):
                continue
            pieces = split_sentences(text, limit) if len(text) > limit else [text]
            for pi, piece in enumerate(pieces):
                units.append(Unit(len(units), bi, cell, pi, piece))
    return units


def pack(units: list[Unit], limit: int) -> list[list[Unit]]:
    """Greedily group consecutive units into segments of at most ``limit`` characters."""
    segments: list[list[Unit]] = []
    size = 0
    for unit in units:
        if segments and size + len(unit.text) <= limit:
            segments[-1].append(unit)
            size += len(unit.text)
        else:
            segments.append([unit])
            size = len(unit.text)
    return segments


def protect(text: str, start: int) -> tuple[str, dict[str, str]]:
    """Replace spans that must not be translated by ``⟦Pn⟧`` tokens numbered from ``start``."""
    spans: dict[str, str] = {}

    def swap(m: re.Match[str]) -> str:
        token = f"⟦P{start + len(spans)}⟧"
        spans[token] = m.group(0)
        return token

    return _PROTECT.sub(swap, text), spans


def restore(text: str, spans: dict[str, str]) -> str:
    return _TOKEN.sub(lambda m: spans.get(m.group(0), m.group(0)), text)


def encode_segment(units: list[Unit]) -> Encoded:
    """Number the units as ``[[n]] text`` lines, protecting spans."""
    lines: list[str] = []
    all_spans: list[dict[str, str]] = []
    count = 0
    for n, unit in enumerate(units, start=1):
        text, spans = protect(unit.text, count + 1)
        count += len(spans)
        all_spans.append(spans)
        lines.append(f"[[{n}]] {text}")
    return Encoded("\n".join(lines), all_spans, units)


def clean_output(raw: str) -> str:
    """Drop ``<think>`` blocks and surrounding whitespace."""
    return _THINK.sub("", raw).strip()


def _parse_wire(text: str) -> list[tuple[int, str]]:
    pairs: list[tuple[int, list[str]]] = []
    for line in text.splitlines():
        m = _MARKER.match(line)
        if m:
            pairs.append((int(m.group(1)), [m.group(2)]))
        elif pairs:
            pairs[-1][1].append(line)
    return [(i, "\n".join(lines).strip()) for i, lines in pairs]


def _last_per_id(pairs: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Collapse runs of the same ID to their last line (models sometimes echo the source first)."""
    out: list[tuple[int, str]] = []
    for pair in pairs:
        if out and out[-1][0] == pair[0]:
            out[-1] = pair
        else:
            out.append(pair)
    return out


def decode_segment(raw: str, enc: Encoded) -> list[str] | None:
    """Parse the model answer; None unless every ID and protected token came back."""
    pairs = _last_per_id(_parse_wire(clean_output(raw)))
    if [i for i, _ in pairs] != list(range(1, len(enc.units) + 1)):
        return None
    out: list[str] = []
    for (_, text), spans in zip(pairs, enc.spans, strict=True):
        if any(token not in text for token in spans):
            return None
        out.append(restore(text, spans))
    return out
