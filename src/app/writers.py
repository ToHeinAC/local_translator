"""Output writers: ``Document`` to md/docx/pdf bytes, file names and MIME types."""

import csv
import io

from openpyxl import Workbook

from app.document import Document, write_markdown
from app.docx_writer import write_docx
from app.glossary import GLOSSARY_TEMPLATE_CSV
from app.pdf_writer import write_pdf

__all__ = [
    "glossary_template_xlsx",
    "mime_type",
    "output_name",
    "write_docx",
    "write_md",
    "write_pdf",
]

_MIME = {
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def output_name(stem: str, target: str, ext: str) -> str:
    """``<stem>_<target>.<ext>``."""
    return f"{stem}_{target}.{ext}"


def mime_type(ext: str) -> str:
    return _MIME[ext]


def write_md(doc: Document) -> bytes:
    return write_markdown(doc).encode()


def glossary_template_xlsx() -> bytes:
    """The template glossary as an Excel workbook (same rows as the CSV template)."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None  # a new workbook always has one sheet
    for row in csv.reader(io.StringIO(GLOSSARY_TEMPLATE_CSV)):
        sheet.append(row)
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()
