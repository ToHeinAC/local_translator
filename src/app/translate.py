"""Translation orchestration with an injected ``llm(prompt) -> str`` (pure, no I/O)."""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.document import Block, Document, Kind
from app.glossary import Entry, Glossary, Match
from app.lang import MIN_CHARS, looks_untranslated
from app.prompt import build_prompt
from app.segment import Cell, Encoded, Unit, decode_segment, encode_segment, pack, plan_units

Llm = Callable[[str], str]
Context = tuple[str, str]  # (source, translation) of the previous segment's last unit
Key = tuple[int, Cell | None]


class FatalLlmError(RuntimeError):
    """An LLM failure that must abort the whole job (e.g. host unreachable), not one segment."""


@dataclass(frozen=True)
class TermMiss:
    block: int
    excerpt: str
    entry: Entry


@dataclass(frozen=True)
class TranslationResult:
    document: Document
    misses: list[TermMiss]
    failed: tuple[int, ...]  # block indices left in the source language
    hits: int  # glossary entries found in the source, per unit
    cancelled: bool

    @property
    def enforced(self) -> int:
        return self.hits - len(self.misses)


def translate_document(
    doc: Document,
    glossary: Glossary,
    llm: Llm,
    *,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    segment_chars: int = 3000,
) -> TranslationResult:
    """Translate all translatable text; structure is kept because only block text changes."""
    units = plan_units(doc, segment_chars, glossary.target_lang)
    segments = pack(units, segment_chars)
    job = _Job(glossary, llm)
    context: Context | None = None
    cancelled = False
    for n, segment in enumerate(segments, start=1):
        context = job.run(segment, context)
        if progress:
            progress(n, len(segments))
        if n < len(segments) and cancel and cancel():
            cancelled = True
            break
    translated = _translations(units, job.done, job.failed)
    failed = tuple(sorted({block for block, _ in job.failed}))
    return TranslationResult(_assemble(doc, translated), job.misses, failed, job.hits, cancelled)


class _Job:
    def __init__(self, glossary: Glossary, llm: Llm) -> None:
        self.glossary = glossary
        self.llm = llm
        self.done: dict[int, str] = {}
        self.failed: set[Key] = set()
        self.misses: list[TermMiss] = []
        self.hits = 0

    def run(self, segment: list[Unit], context: Context | None) -> Context | None:
        matches = [self.glossary.match(u.text) for u in segment]
        self.hits += sum(len(m) for m in matches)
        outs: list[str | None]
        try:
            group = self._group(segment, matches, context)
            outs = list(group) if group is not None else self._fallback(segment, matches, context)
        except FatalLlmError:
            raise
        except Exception:
            outs = [None] * len(segment)
        self._record(segment, matches, outs)
        return self._next_context(segment, outs, context)

    def _next_context(
        self, segment: list[Unit], outs: list[str | None], context: Context | None
    ) -> Context | None:
        """The last unit as context, unless it (or its whole segment) is an echo or failed."""
        good = [o for o in outs if o is not None]
        last = outs[-1]
        if last is None or self._echoed(segment[-1:], [last]):
            return context
        if len(good) == len(outs) and self._echoed(segment, good):
            return context  # never let an echo prime the next segment
        return (segment[-1].text, last)

    def _fallback(
        self, segment: list[Unit], matches: list[list[Match]], context: Context | None
    ) -> list[str | None]:
        """Translate the halves of an unusable segment, recursing down to single units."""
        if len(segment) == 1:
            return [None]
        mid = len(segment) // 2
        outs: list[str | None] = []
        for part, found in ((segment[:mid], matches[:mid]), (segment[mid:], matches[mid:])):
            group = self._try_group(part, found, context)
            outs += list(group) if group is not None else self._fallback(part, found, context)
        return outs

    def _try_group(
        self, segment: list[Unit], matches: list[list[Match]], context: Context | None
    ) -> list[str] | None:
        """``_group``, with any non-fatal error counting as an unusable answer."""
        try:
            return self._group(segment, matches, context)
        except FatalLlmError:
            raise
        except Exception:
            return None

    def _group(
        self, segment: list[Unit], matches: list[list[Match]], context: Context | None
    ) -> list[str] | None:
        """Translate one segment; at most one retry. None if the answer stays unusable."""
        enc = encode_segment(segment)
        entries = _entries(matches)
        first = self._call(enc, entries, context, False, [], False)
        missed = self._missed(matches, first) if first is not None else []
        echoed = first is not None and self._echoed(segment, first)
        if first is not None and not missed and not echoed:
            return first
        retry = self._call(enc, entries, context, True, missed, echoed)
        return retry if retry is not None else first

    def _call(
        self,
        enc: Encoded,
        entries: list[Entry],
        context: Context | None,
        strict: bool,
        missed: list[Entry],
        untranslated: bool,
    ) -> list[str] | None:
        g = self.glossary
        prompt = build_prompt(
            enc.body,
            g.source_lang,
            g.target_lang,
            entries,
            context,
            strict=strict,
            missed=missed,
            untranslated=untranslated,
        )
        return decode_segment(self.llm(prompt), enc)

    def _echoed(self, segment: list[Unit], outs: list[str]) -> bool:
        """True if any long unit, or the segment as a whole, still reads as the source language."""
        src, tgt = self.glossary.source_lang, self.glossary.target_lang
        whole = looks_untranslated(" ".join(u.text for u in segment), " ".join(outs), src, tgt)
        return whole or any(
            looks_untranslated(u.text, o, src, tgt) for u, o in zip(segment, outs, strict=True)
        )

    def _missed(self, matches: list[list[Match]], outs: list[str]) -> list[Entry]:
        missed: list[Entry] = []
        for found, text in zip(matches, outs, strict=True):
            missed += [e for e in self.glossary.verify(text, found) if e not in missed]
        return missed

    def _record(
        self, segment: list[Unit], matches: list[list[Match]], outs: list[str | None]
    ) -> None:
        for unit, found, out in zip(segment, matches, outs, strict=True):
            if out is None:
                self.failed.add((unit.block, unit.cell))
                continue
            for entry in self.glossary.verify(out, found):
                self.misses.append(TermMiss(unit.block, unit.text[:80], entry))
            if _unchanged(unit.text, out):  # the model handed the source back
                self.failed.add((unit.block, unit.cell))
            else:
                self.done[unit.idx] = out


def _unchanged(source: str, out: str) -> bool:
    """The model handed back a long source text that is not just a list of names."""
    same = " ".join(out.split()) == " ".join(source.split())
    return len(source) >= MIN_CHARS and same and not _name_like(source)


def _name_like(text: str) -> bool:
    """Mostly capitalised words (names, titles); German nouns alone stay well below 70 %."""
    words = re.findall(r"[^\W\d_]+", text)
    return not words or sum(w[0].isupper() for w in words) >= 0.7 * len(words)


def _entries(matches: list[list[Match]]) -> list[Entry]:
    entries: list[Entry] = []
    for found in matches:
        entries += [m.entry for m in found if m.entry not in entries]
    return entries


def _translations(units: list[Unit], done: dict[int, str], failed: set[Key]) -> dict[Key, str]:
    """Join the pieces of each block/cell; keys with any untranslated piece are left out."""
    groups: dict[Key, list[Unit]] = {}
    for unit in units:
        groups.setdefault((unit.block, unit.cell), []).append(unit)
    return {
        key: " ".join(done[u.idx] for u in group)
        for key, group in groups.items()
        if key not in failed and all(u.idx in done for u in group)
    }


def _assemble(doc: Document, translated: dict[Key, str]) -> Document:
    out: Document = []
    for bi, block in enumerate(doc):
        if block.kind is Kind.TABLE:
            rows = tuple(
                tuple(translated.get((bi, (r, c)), text) for c, text in enumerate(row))
                for r, row in enumerate(block.rows)
            )
            out.append(replace(block, rows=rows))
        else:
            out.append(_text_block(block, translated.get((bi, None))))
    return out


def _text_block(block: Block, text: str | None) -> Block:
    return block if text is None else replace(block, text=text)
