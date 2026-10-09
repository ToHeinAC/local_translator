"""DOCX in-place translation (python-docx): text is replaced run by run, nothing else is touched."""

# python-docx exposes its lxml elements untyped; this adapter is one of the places that touch them.
# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnknownParameterType=false
# pyright: reportMissingParameterType=false

import copy
import io
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from docx import Document as load_docx
from docx.enum.text import WD_COLOR_INDEX
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.document import Block, Document, DocumentReadError, Kind
from app.docx_reader import read_docx
from app.glossary import Glossary
from app.run_tags import Piece, decode, encode, strip_tags, tag_counts
from app.translate import Llm, TranslationResult, translate_document

_P, _R, _T, _RPR = qn("w:p"), qn("w:r"), qn("w:t"), qn("w:rPr")
_LINK, _BR, _TYPE = qn("w:hyperlink"), qn("w:br"), qn("w:type")
_TRANSPARENT = {qn("w:pPr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd"), qn("w:proofErr")}
_RUN_CHILDREN = {_RPR, _T, qn("w:tab")}
_UNTOUCHED_PARTS = {
    "/word/footnotes.xml": ("footnotes", "w:footnote"),
    "/word/endnotes.xml": ("endnotes", "w:endnote"),
    "/word/comments.xml": ("comments", "w:comment"),
}


@dataclass(frozen=True)
class InplaceResult:
    data: bytes  # the translated DOCX
    document: Document  # the same text as blocks, for the md/pdf writers
    translation: TranslationResult  # blocks here are text groups, see ``translate_docx``
    untouched: tuple[str, ...]  # features that were not translated (footnotes, comments, ...)


@dataclass
class _Slot:
    """A group of adjacent text runs/hyperlinks of one paragraph: one translation unit."""

    par: Paragraph
    items: list[Any]  # w:r / w:hyperlink children of w:p, in order
    runs: list[Any]  # every w:r inside ``items``
    pieces: list[Piece]  # one per run

    @property
    def tagged(self) -> str:
        return encode(self.pieces)

    def template(self, piece: Piece) -> Any:
        """The source run to copy font properties from: same format, else same link, else first."""
        same_link = [r for r, p in zip(self.runs, self.pieces, strict=True) if p.link == piece.link]
        exact = [r for r, p in zip(self.runs, self.pieces, strict=True) if p.key == piece.key]
        return (exact or same_link or self.runs)[0]


def translate_docx(
    data: bytes,
    glossary: Glossary,
    llm: Llm,
    *,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    segment_chars: int = 3000,
) -> InplaceResult:
    """Translate body, table, header and footer text in place; ``translation.failed`` and
    ``misses`` refer to the text groups in document order, not to ``document`` blocks."""
    doc = _load(data)
    slots = [s for p in _paragraphs(doc) for s in _slots(Paragraph(p, doc))]
    blocks = [Block(Kind.PARAGRAPH, s.tagged) for s in slots]  # FR-6a skip: plan_units
    result = translate_document(
        blocks, glossary, llm, progress=progress, cancel=cancel, segment_chars=segment_chars
    )
    for slot, block in zip(slots, result.document, strict=True):
        if block.text != slot.tagged:
            _apply(slot, block.text)
    for index in {m.block for m in result.misses}:
        _highlight(slots[index].par)
    doc.core_properties.language = glossary.target_lang
    out = io.BytesIO()
    doc.save(out)
    return InplaceResult(out.getvalue(), read_docx(out.getvalue()), result, _untouched(doc))


def _load(data: bytes) -> Any:
    try:
        return load_docx(io.BytesIO(data))
    except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise DocumentReadError("Ungültige oder beschädigte DOCX-Datei") from exc


def _roots(doc: Any) -> Iterator[Any]:
    yield doc.element.body
    for section in doc.sections:
        for part in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            if not part.is_linked_to_previous:
                yield part._element


def _paragraphs(doc: Any) -> Iterator[Any]:
    for root in _roots(doc):
        for p in root.iter(_P):
            if not p.xpath("ancestor::w:txbxContent"):
                yield p


def _slots(par: Paragraph) -> list[_Slot]:
    slots: list[_Slot] = []
    group: list[Any] = []
    depth = 0
    for child in par._p.iterchildren():
        if child.tag in _TRANSPARENT:
            continue
        depth, text = _classify(child, depth)
        if text:
            group.append(child)
            continue
        slots += _flush(par, group)
        group = []
    return slots + _flush(par, group)


def _classify(child: Any, depth: int) -> tuple[int, bool]:
    """Track complex-field nesting; True if ``child`` is plain translatable text."""
    if child.tag == _LINK:
        return depth, depth == 0 and all(r.tag == _R and _is_text(r) for r in child)
    if child.tag != _R:
        return depth, False
    for fld in child.iterchildren(qn("w:fldChar")):
        kind = fld.get(qn("w:fldCharType"))
        depth += 1 if kind == "begin" else -1 if kind == "end" else 0
    return depth, depth == 0 and _is_text(child)


def _is_text(run: Any) -> bool:
    return all(
        c.tag in _RUN_CHILDREN or (c.tag == _BR and c.get(_TYPE) in (None, "textWrapping"))
        for c in run
    )


def _flush(par: Paragraph, items: list[Any]) -> list[_Slot]:
    runs: list[Any] = []
    pieces: list[Piece] = []
    links = 0
    for item in items:
        if item.tag == _LINK:
            links += 1
            members = [(r, links) for r in item.findall(_R)]
        else:
            members = [(item, 0)]
        for element, link in members:
            run = Run(element, par)
            pieces.append(
                Piece(run.text, bool(run.bold), bool(run.italic), bool(run.underline), link)
            )
            runs.append(element)
    if not any(ch.isalpha() for p in pieces for ch in p.text):
        return []
    return [_Slot(par, items, runs, pieces)]


def _apply(slot: _Slot, text: str) -> None:
    pieces = decode(text, tag_counts(slot.tagged))
    exact = pieces is not None
    new = [(p.link, _new_run(slot, p, exact)) for p in pieces or [Piece(strip_tags(text))]]
    anchor = slot.items[0]
    parent = anchor.getparent()
    index = parent.index(anchor)
    links = [i for i in slot.items if i.tag == _LINK]
    for item in slot.items:
        parent.remove(item)
    for link in links:
        for old in link.findall(_R):
            link.remove(old)
    order: list[Any] = []
    for link_no, element in new:
        if link_no and exact:
            holder = links[link_no - 1]
            if holder not in order:
                order.append(holder)
            holder.append(element)
        else:
            order.append(element)
    for offset, element in enumerate(order):
        parent.insert(index + offset, element)


def _new_run(slot: _Slot, piece: Piece, exact: bool) -> Any:
    element = copy.deepcopy(slot.template(piece) if exact else slot.runs[0])
    for child in list(element):
        if child.tag != _RPR:
            element.remove(child)
    run = Run(element, slot.par)
    run.text = piece.text
    if exact:
        for attr, want in (("bold", piece.bold), ("italic", piece.italic)):
            if bool(getattr(run, attr)) != want:
                setattr(run, attr, want)
        if bool(run.underline) != piece.underline:
            run.underline = piece.underline
    return element


def _highlight(par: Paragraph) -> None:
    for element in par._p.iter(_R):
        if element.find(_T) is not None:
            Run(element, par).font.highlight_color = WD_COLOR_INDEX.YELLOW


def _untouched(doc: Any) -> tuple[str, ...]:
    found: list[str] = []
    for part in doc.part.package.iter_parts():
        label, tag = _UNTOUCHED_PARTS.get(str(part.partname), ("", ""))
        if label and _has_text(parse_xml(part.blob), tag):
            found.append(label)
    if any(root.xpath(".//w:txbxContent//w:t") for root in _roots(doc)):
        found.append("text boxes")
    return tuple(found)


def _has_text(root: Any, tag: str) -> bool:
    return any(
        next(n.iter(_T), None) is not None and n.get(qn("w:type")) is None
        for n in root.iter(qn(tag))
    )
