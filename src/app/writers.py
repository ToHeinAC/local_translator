"""Output writers: ``Document`` to md/docx/pdf bytes, file names and MIME types."""

from app.docx_writer import write_docx
from app.document import Document, write_markdown
from app.pdf_writer import write_pdf

__all__ = ["mime_type", "output_name", "write_docx", "write_md", "write_pdf"]

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
