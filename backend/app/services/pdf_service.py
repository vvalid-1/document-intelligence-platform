from __future__ import annotations

import uuid
from pathlib import Path

import fitz  # PyMuPDF

from app.core.config import settings
from app.utils.file_utils import make_document_dir

_PAGE_W = 595  # A4 width in points
_PAGE_H = 842  # A4 height in points
_MARGIN_X = 72  # 1 inch horizontal margin
_MARGIN_TOP = 72
_MARGIN_BOTTOM = 72
_FONT = "helv"
_FONT_SIZE = 11
_LINE_H = 16  # line height in points
_MAX_CHARS = 85  # approximate chars per line at Helvetica 11pt on A4


def generate_pdf_from_text(text: str, output_path: Path) -> None:
    """Write text to a simple multi-page A4 PDF using PyMuPDF."""
    doc = fitz.open()

    def _new_page() -> tuple[fitz.Page, float]:
        return doc.new_page(width=_PAGE_W, height=_PAGE_H), float(_MARGIN_TOP)

    page, y = _new_page()

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        display_lines = _wrap(raw_line) if raw_line.strip() else [""]
        for line in display_lines:
            if y + _LINE_H > _PAGE_H - _MARGIN_BOTTOM:
                page, y = _new_page()
            if line:
                page.insert_text((_MARGIN_X, y), line, fontname=_FONT, fontsize=_FONT_SIZE)
            y += _LINE_H

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()


def _wrap(line: str) -> list[str]:
    words = line.split()
    result: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= _MAX_CHARS:
            current = candidate
        else:
            if current:
                result.append(current)
            current = word
    if current:
        result.append(current)
    return result or [""]


def save_version_files(
    document_id: uuid.UUID,
    version_number: int,
    edited_text: str,
    stem_suffix: str = "edited",
) -> tuple[str, str]:
    """
    Write text as .txt and .pdf into the document's upload directory.
    Returns (txt_relative_path, pdf_relative_path).
    """
    doc_dir = make_document_dir(str(document_id))
    stem = f"v{version_number}_{stem_suffix}"

    txt_path = doc_dir / f"{stem}.txt"
    txt_path.write_text(edited_text, encoding="utf-8")

    pdf_path = doc_dir / f"{stem}.pdf"
    generate_pdf_from_text(edited_text, pdf_path)

    txt_rel = f"{document_id}/{stem}.txt"
    pdf_rel = f"{document_id}/{stem}.pdf"
    return txt_rel, pdf_rel
