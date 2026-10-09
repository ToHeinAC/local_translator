"""Run formatting as inline tags for DOCX in-place translation (pure)."""

import re
from collections import Counter
from dataclasses import dataclass
from itertools import groupby

_TAG = re.compile(r"<(/?)(a\d+|b|i|u)>")


@dataclass(frozen=True)
class Piece:
    """Text with one formatting; ``link`` is the 1-based hyperlink number (0 = none)."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    link: int = 0

    @property
    def key(self) -> tuple[int, bool, bool, bool]:
        return (self.link, self.bold, self.italic, self.underline)


def encode(pieces: list[Piece]) -> str:
    """Tagged text: ``<a1>`` outermost, then ``<b>``, ``<i>``, ``<u>``; same formats are merged."""
    out: list[str] = []
    for link, in_link in groupby(pieces, key=lambda p: p.link):
        inner = ""
        for (b, i, u), same in groupby(in_link, key=lambda p: (p.bold, p.italic, p.underline)):
            inner += _wrap("".join(p.text for p in same), b, i, u)
        out.append(f"<a{link}>{inner}</a{link}>" if link else inner)
    return "".join(out)


def _wrap(text: str, bold: bool, italic: bool, underline: bool) -> str:
    for flag, tag in ((underline, "u"), (italic, "i"), (bold, "b")):
        if flag:
            text = f"<{tag}>{text}</{tag}>"
    return text


def tag_counts(tagged: str) -> Counter[str]:
    """Opening tags by name; a translation must reproduce exactly these."""
    return Counter(m.group(2) for m in _TAG.finditer(tagged) if not m.group(1))


def strip_tags(text: str) -> str:
    return _TAG.sub("", text)


def decode(text: str, expected: Counter[str]) -> list[Piece] | None:
    """Pieces of a translated tagged text; None if tags are unbalanced, invented or missing."""
    pieces: list[Piece] = []
    stack: list[str] = []
    opened: Counter[str] = Counter()
    pos = 0
    for m in _TAG.finditer(text):
        _add(pieces, text[pos : m.start()], stack)
        pos = m.end()
        if m.group(1):
            if not stack or stack.pop() != m.group(2):
                return None
        else:
            stack.append(m.group(2))
            opened[m.group(2)] += 1
    _add(pieces, text[pos:], stack)
    return pieces if not stack and opened == expected else None


def _add(pieces: list[Piece], text: str, stack: list[str]) -> None:
    if text:
        link = next((int(n[1:]) for n in stack if n[0] == "a"), 0)
        pieces.append(Piece(text, "b" in stack, "i" in stack, "u" in stack, link))
