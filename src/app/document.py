"""Document model: blocks with Markdown inline text, plus Markdown parse/write (pure, no I/O)."""

import re
from dataclasses import dataclass
from enum import StrEnum

from markdown_it import MarkdownIt
from markdown_it.token import Token


class Kind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    QUOTE = "quote"
    CODE = "code"
    IMAGE_PLACEHOLDER = "image_placeholder"
    PAGE_BREAK = "page_break"


@dataclass(frozen=True)
class Block:
    """One structural unit. ``text`` is Markdown inline syntax (raw content for code)."""

    kind: Kind
    text: str = ""
    level: int = 0  # heading level 1-6
    depth: int = 0  # list nesting, 0-based
    ordered: bool = False
    rows: tuple[tuple[str, ...], ...] = ()  # table cells, first row is the header
    info: str = ""  # code fence info string
    translate: bool = True


Document = list[Block]


class EmptyDocumentError(ValueError):
    """The document has no translatable text."""


_IMAGE_ONLY = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_NO_TEXT = {Kind.IMAGE_PLACEHOLDER, Kind.PAGE_BREAK}
_MD = MarkdownIt("commonmark").enable("table")


def parse_markdown(source: str) -> Document:
    """Parse Markdown into blocks; raise ``EmptyDocumentError`` if no text remains."""
    doc = _Parser(_MD.parse(source)).run()
    if not any(b.kind not in _NO_TEXT and (b.text.strip() or b.rows) for b in doc):
        raise EmptyDocumentError("Dokument enthält keinen Text")
    return doc


class _Parser:
    """Flattens markdown-it tokens into blocks (list/quote nesting is flattened, see docs)."""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._blocks: Document = []
        self._lists: list[bool] = []  # ordered flag per open list
        self._quote = 0
        self._item_open = False  # current list item still waits for its first paragraph
        self._rows: list[list[str]] = []

    def run(self) -> Document:
        for i, tok in enumerate(self._tokens):
            self._token(tok, self._tokens[i + 1] if i + 1 < len(self._tokens) else tok)
        return self._blocks

    def _token(self, tok: Token, nxt: Token) -> None:
        kind = tok.type
        if kind in ("bullet_list_open", "ordered_list_open"):
            self._lists.append(kind == "ordered_list_open")
        elif kind in ("bullet_list_close", "ordered_list_close"):
            self._lists.pop()
        elif kind == "list_item_open":
            self._item_open = True
        elif kind == "blockquote_open":
            self._quote += 1
        elif kind == "blockquote_close":
            self._quote -= 1
        elif kind == "heading_open":
            self._blocks.append(Block(Kind.HEADING, nxt.content, level=int(tok.tag[1])))
        elif kind == "paragraph_open":
            self._paragraph(nxt.content)
        elif kind in ("fence", "code_block"):
            text = tok.content.rstrip("\n")
            self._blocks.append(Block(Kind.CODE, text, info=tok.info.strip(), translate=False))
        elif kind == "html_block":
            self._blocks.append(Block(Kind.PARAGRAPH, tok.content.strip(), translate=False))
        elif kind == "hr":
            self._blocks.append(Block(Kind.PAGE_BREAK, translate=False))
        elif kind.startswith(("table_", "tr_", "th_", "td_")) or kind == "inline":
            self._table(tok)

    def _paragraph(self, text: str) -> None:
        if self._lists and self._item_open:
            self._item_open = False
            block = Block(
                Kind.LIST_ITEM, text, depth=len(self._lists) - 1, ordered=self._lists[-1]
            )
        elif self._quote:
            block = Block(Kind.QUOTE, text)
        elif m := _IMAGE_ONLY.fullmatch(text.strip()):
            block = Block(Kind.IMAGE_PLACEHOLDER, f"[Bild: {m.group(1)}]", translate=False)
        else:
            block = Block(Kind.PARAGRAPH, text)
        self._blocks.append(block)

    def _table(self, tok: Token) -> None:
        if tok.type == "tr_open":
            self._rows.append([])
        elif tok.type == "inline" and self._rows and tok.level >= 4:
            self._rows[-1].append(tok.content)
        elif tok.type == "table_close":
            rows = tuple(tuple(r) for r in self._rows)
            self._rows = []
            self._blocks.append(Block(Kind.TABLE, rows=rows))


def write_markdown(doc: Document) -> str:
    """Serialise blocks to canonical Markdown (inverse of ``parse_markdown``)."""
    out: list[str] = []
    widths: list[int] = []
    counters: dict[int, int] = {}
    prev: Block | None = None
    for block in doc:
        if block.kind is Kind.LIST_ITEM:
            piece = _list_item(block, widths, counters)
        else:
            widths.clear()
            counters.clear()
            piece = _piece(block)
        if prev is not None:
            out.append(_separator(prev, block))
        out.append(piece)
        prev = block
    return "".join(out) + "\n"


def _separator(prev: Block, block: Block) -> str:
    if prev.kind is Kind.LIST_ITEM and block.kind is Kind.LIST_ITEM:
        new_list = block.depth == 0 and block.ordered != prev.ordered
        return "\n\n" if new_list else "\n"
    if prev.kind is Kind.QUOTE and block.kind is Kind.QUOTE:
        return "\n>\n"
    return "\n\n"


def _list_item(block: Block, widths: list[int], counters: dict[int, int]) -> str:
    d = block.depth
    del widths[d:]
    for deeper in [k for k in counters if k > d]:
        del counters[deeper]
    while len(widths) < d:
        widths.append(2)
    if block.ordered:
        counters[d] = counters.get(d, 0) + 1
        marker = f"{counters[d]}. "
    else:
        counters.pop(d, None)
        marker = "- "
    widths.append(len(marker))
    return " " * sum(widths[:d]) + marker + block.text


def _piece(block: Block) -> str:
    match block.kind:
        case Kind.HEADING:
            return "#" * block.level + " " + block.text
        case Kind.QUOTE:
            return "\n".join("> " + line for line in block.text.split("\n"))
        case Kind.CODE:
            return _fence(block)
        case Kind.TABLE:
            return _table(block.rows)
        case Kind.PAGE_BREAK:
            return "---"
        case _:
            return block.text


def _fence(block: Block) -> str:
    runs = [len(m) for m in re.findall(r"`+", block.text)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return f"{fence}{block.info}\n{block.text}\n{fence}"


def _table(rows: tuple[tuple[str, ...], ...]) -> str:
    lines = ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    lines.insert(1, "|" + "---|" * len(rows[0]))
    return "\n".join(lines)


def _cell(text: str) -> str:
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def _shape(block: Block) -> tuple[object, ...]:
    rows = tuple(len(r) for r in block.rows)
    return (block.kind, block.level, block.depth, block.ordered, rows)


def same_structure(a: Document, b: Document) -> bool:
    """True if both documents have the same kinds, heading levels, list depths and table shapes."""
    return len(a) == len(b) and all(_shape(x) == _shape(y) for x, y in zip(a, b, strict=True))
