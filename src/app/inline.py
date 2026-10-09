"""Markdown inline text to flat formatted runs (pure; shared by the DOCX and PDF writers)."""

from dataclasses import dataclass

from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark")
_TEXT = {"text", "text_special", "html_inline"}


@dataclass(frozen=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    href: str = ""


def parse_inline(text: str) -> list[Run]:
    """Split Markdown inline syntax into runs; soft breaks become spaces, hard breaks ``\\n``."""
    bold = italic = 0
    hrefs: list[str] = []
    runs: list[Run] = []
    root = _MD.parseInline(text)[0]
    for tok in root.children or []:
        kind = tok.type
        if kind in ("strong_open", "strong_close"):
            bold += 1 if kind == "strong_open" else -1
        elif kind in ("em_open", "em_close"):
            italic += 1 if kind == "em_open" else -1
        elif kind == "link_open":
            hrefs.append(str(tok.attrGet("href") or ""))
        elif kind == "link_close":
            hrefs.pop()
        else:
            content = _content(tok.type, tok.content)
            if content:
                href = hrefs[-1] if hrefs else ""
                runs.append(Run(content, bool(bold), bool(italic), kind == "code_inline", href))
    return runs


def _content(kind: str, content: str) -> str:
    if kind in _TEXT or kind == "code_inline":
        return content
    if kind == "softbreak":
        return " "
    if kind == "hardbreak":
        return "\n"
    if kind == "image":
        return f"[Bild: {content}]"
    return ""
