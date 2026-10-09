"""One translation job from file bytes to the three outputs (pure, in memory)."""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from app.document import Document, DocumentReadError, EmptyDocumentError, write_markdown
from app.docx_inplace import translate_docx
from app.glossary import Glossary
from app.lang import detect_language
from app.readers import read_document
from app.run_tags import strip_tags
from app.translate import Llm, TranslationResult, translate_document
from app.writers import write_docx, write_md, write_pdf

_EXCERPT = 80


@dataclass(frozen=True)
class JobResult:
    stem: str
    target: str
    document: Document  # translated text as blocks (preview, md, pdf)
    md: bytes
    docx: bytes
    pdf: bytes
    translation: TranslationResult
    untouched: tuple[str, ...]  # DOCX features that were not translated
    marked: tuple[int, ...] = ()  # ``document`` blocks left in the source language

    @property
    def hits(self) -> int:
        return self.translation.hits

    @property
    def enforced(self) -> int:
        return self.translation.enforced

    @property
    def cancelled(self) -> bool:
        return self.translation.cancelled


@dataclass(frozen=True)
class UploadInfo:
    language: str | None  # detected source language, if supported
    error: str  # user-facing message, empty if the file is readable


def inspect_upload(name: str, data: bytes) -> UploadInfo:
    """Read the file once to detect its language and surface read errors before the job."""
    try:
        doc = read_document(name, data)
    except (DocumentReadError, EmptyDocumentError) as exc:
        return UploadInfo(None, str(exc))
    text = " ".join(b.text for b in doc if b.text)
    return UploadInfo(detect_language(text), "")


def run_job(
    name: str,
    data: bytes,
    glossary: Glossary,
    llm: Llm,
    *,
    user: str,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    segment_chars: int = 3000,
) -> JobResult:
    """Translate ``data``; a DOCX is translated in place, everything else is rebuilt."""
    stem = Path(name).stem
    target = glossary.target_lang
    if Path(name).suffix.lower() == ".docx":
        inplace = translate_docx(
            data, glossary, llm, progress=progress, cancel=cancel, segment_chars=segment_chars
        )
        document, docx = inplace.document, inplace.data
        translation, untouched = inplace.translation, inplace.untouched
        marked: tuple[int, ...] = ()  # DOCX failures index text groups, not document blocks
    else:
        translation = translate_document(
            read_document(name, data),
            glossary,
            llm,
            progress=progress,
            cancel=cancel,
            segment_chars=segment_chars,
        )
        document, untouched, marked = translation.document, (), translation.failed
        docx = write_docx(document, title=stem, language=target, author=user)
    pdf = write_pdf(document, title=stem, author=user)
    md = write_md(document)
    return JobResult(stem, target, document, md, docx, pdf, translation, untouched, marked)


def report_csv(result: JobResult) -> bytes:
    """Term misses, failed blocks and untouched features as CSV (UTF-8 with BOM for Excel)."""
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(["kind", "detail", "source", "expected"])
    for miss in result.translation.misses:
        out.writerow(["term", miss.excerpt, miss.entry.source, miss.entry.target])
    for excerpt in failed_excerpts(result):
        out.writerow(["failed", excerpt, "", ""])
    for feature in result.untouched:
        out.writerow(["untouched", feature, "", ""])
    return b"\xef\xbb\xbf" + buf.getvalue().encode()


def failed_excerpts(result: JobResult) -> list[str]:
    """The start of each text that stayed in the source language."""
    blocks = [result.translation.document[i] for i in result.translation.failed]
    texts = [b.text or " | ".join(c for row in b.rows for c in row) for b in blocks]
    return [strip_tags(t)[:_EXCERPT] for t in texts]


def preview_markdown(result: JobResult) -> str:
    """Markdown for the on-screen preview: failed blocks marked with ⚠️, ``$`` escaped (no LaTeX)."""
    marked = [
        replace(b, text=f"⚠️ {b.text}") if i in result.marked and b.text else b
        for i, b in enumerate(result.document)
    ]
    return write_markdown(marked).replace("$", r"\$")
