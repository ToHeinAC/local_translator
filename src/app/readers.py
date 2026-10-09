"""Input adapters: raw file bytes to structured data."""

import csv
import io
import re
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.document import (
    Block,
    Document,
    DocumentReadError,
    EmptyDocumentError,
    Kind,
    parse_markdown,
    require_text,
)
from app.docx_reader import read_docx
from app.glossary import GlossaryError
from app.pdf_reader import read_pdf


def read_glossary_rows(name: str, data: bytes) -> list[list[str]]:
    """Read a csv/tsv/xlsx/md glossary into rows of stripped strings (first row = header)."""
    ext = Path(name).suffix.lower()
    if ext in (".csv", ".tsv"):
        return _read_delimited(data)
    if ext == ".xlsx":
        return _read_xlsx(data)
    if ext == ".md":
        return _read_md_table(data)
    raise GlossaryError(f"Dateityp '{ext}' wird für Glossare nicht unterstützt")


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _read_delimited(data: bytes) -> list[list[str]]:
    text = _decode(data)
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = max(",;\t", key=first.count)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    return [[c.strip() for c in row] for row in reader]


def _read_xlsx(data: bytes) -> list[list[str]]:
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError) as exc:
        raise GlossaryError("Ungültige xlsx-Datei") from exc
    sheet = book.worksheets[0]
    return [
        ["" if c is None else str(c).strip() for c in row]
        for row in sheet.iter_rows(values_only=True)
    ]


def _read_md_table(data: bytes) -> list[list[str]]:
    try:
        doc = parse_markdown(_decode(data))
    except EmptyDocumentError as exc:
        raise GlossaryError("Keine Tabelle im Markdown-Glossar gefunden") from exc
    for block in doc:
        if block.kind is Kind.TABLE:
            return [[c.strip() for c in row] for row in block.rows]
    raise GlossaryError("Keine Tabelle im Markdown-Glossar gefunden")


def read_document(name: str, data: bytes) -> Document:
    """Read a docx/md/txt/pdf file into blocks. Errors are ``DocumentReadError`` or
    ``EmptyDocumentError``, both with user-facing messages."""
    ext = Path(name).suffix.lower()
    if ext == ".docx":
        return read_docx(data)
    if ext == ".pdf":
        return read_pdf(data)
    if ext == ".md":
        return parse_markdown(_decode(data))
    if ext == ".txt":
        return _read_txt(_decode(data))
    raise DocumentReadError(f"Dateityp '{ext}' wird nicht unterstützt")


def _read_txt(text: str) -> Document:
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    return require_text([Block(Kind.PARAGRAPH, p) for p in paragraphs if p])
