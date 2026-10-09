"""Glossary: build entries for a language pair, match source terms, verify target terms (pure)."""

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

GLOSSARY_TEMPLATE_CSV = (
    "de,en,fr,note\n"
    "Abklingbecken,spent fuel pool,piscine de désactivation,\n"
    'Freigabe,clearance,libération,"radiologische Bedeutung, nicht ""approval"""\n'
)

_SUFFIXES = "e|en|er|es|n|s"
_COMPOUND_LANGS = frozenset({"de"})  # terms may also end a compound noun


class GlossaryError(ValueError):
    """The glossary file cannot be used (message is shown to the user)."""


@dataclass(frozen=True)
class Entry:
    source: str
    target: str
    note: str
    row: int  # 1-based spreadsheet row (header = 1)


@dataclass(frozen=True)
class Issue:
    row: int
    kind: Literal["empty_cell", "duplicate", "conflict"]
    detail: str


@dataclass(frozen=True)
class Match:
    entry: Entry
    count: int  # occurrences of the source term in the segment


@dataclass(frozen=True)
class Glossary:
    source_lang: str
    target_lang: str
    entries: tuple[Entry, ...]

    def match(self, text: str) -> list[Match]:
        """Entries whose source term occurs in ``text``; longest terms claim their span first."""
        low = text.casefold()
        compound = self.source_lang in _COMPOUND_LANGS
        claimed: list[tuple[int, int]] = []
        found: list[Match] = []
        for entry in sorted(self.entries, key=lambda e: -len(e.source)):
            if entry.source.casefold() not in low:
                continue
            count = _claim(_pattern(entry.source, compound), text, claimed)
            if count:
                found.append(Match(entry, count))
        return sorted(found, key=lambda m: m.entry.row)

    def verify(self, translation: str, matches: list[Match]) -> list[Entry]:
        """Entries whose target term occurs fewer times in ``translation`` than required."""
        compound = self.target_lang in _COMPOUND_LANGS
        return [
            m.entry
            for m in matches
            if len(_pattern(m.entry.target, compound).findall(translation)) < m.count
        ]


@dataclass(frozen=True)
class GlossaryResult:
    glossary: Glossary
    issues: list[Issue]


@lru_cache(maxsize=20000)
def _pattern(term: str, compound: bool) -> re.Pattern[str]:
    start = "" if compound else r"(?<!\w)"
    return re.compile(f"{start}{re.escape(term)}(?:{_SUFFIXES})?(?!\\w)", re.IGNORECASE)


def _claim(pattern: re.Pattern[str], text: str, claimed: list[tuple[int, int]]) -> int:
    count = 0
    for m in pattern.finditer(text):
        span = m.span()
        if any(span[0] < end and start < span[1] for start, end in claimed):
            continue
        claimed.append(span)
        count += 1
    return count


def build_glossary(rows: list[list[str]], source_lang: str, target_lang: str) -> GlossaryResult:
    """Build the glossary for one language pair from table rows (first row = header)."""
    header = [c.strip().lower() for c in rows[0]] if rows else []
    langs = [c for c in header if c and c != "note"]
    for lang in (source_lang, target_lang):
        if lang not in header:
            raise GlossaryError(f"Sprache '{lang}' fehlt im Glossar. Verfügbar: {', '.join(langs)}")
    cols = (header.index(source_lang), header.index(target_lang))
    note_col = header.index("note") if "note" in header else -1
    issues: list[Issue] = []
    groups: dict[str, list[Entry]] = defaultdict(list)
    for number, row in enumerate(rows[1:], start=2):
        cells = [c.strip() for c in row] + [""] * len(header)
        src, tgt = cells[cols[0]], cells[cols[1]]
        if not src and not tgt:
            continue
        if not src or not tgt:
            issues.append(Issue(number, "empty_cell", "Quell- oder Zielbegriff fehlt"))
            continue
        note = cells[note_col] if note_col >= 0 else ""
        groups[src.casefold()].append(Entry(src, tgt, note, number))
    entries = _resolve(groups, issues)
    issues.sort(key=lambda i: i.row)
    return GlossaryResult(Glossary(source_lang, target_lang, entries), issues)


def _resolve(groups: dict[str, list[Entry]], issues: list[Issue]) -> tuple[Entry, ...]:
    kept: list[Entry] = []
    for group in groups.values():
        first = group[0]
        if all(e.target == first.target for e in group):
            kept.append(first)
            issues.extend(Issue(e.row, "duplicate", e.source) for e in group[1:])
        else:
            issues.extend(Issue(e.row, "conflict", e.source) for e in group)
    return tuple(sorted(kept, key=lambda e: e.row))
