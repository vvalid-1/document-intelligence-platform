from __future__ import annotations

import base64
import uuid
from pathlib import Path

import fitz  # PyMuPDF

from app.utils.file_utils import make_document_dir

# Typed signature appearance
_SIG_FONT = "helv"
_SIG_FONT_SIZE = 14
_SIG_COLOR = (0.0, 0.0, 0.6)  # dark blue

# Drawn signature default rect size in points
_DRAWN_WIDTH = 150.0
_DRAWN_HEIGHT = 50.0


# ── PDF inspection ────────────────────────────────────────────────────────────

def get_pdf_page_info(pdf_path: Path, page_number: int) -> tuple[float, float, int]:
    """Return (page_width, page_height, total_pages). page_number is 1-indexed."""
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    if page_number < 1 or page_number > total:
        doc.close()
        raise ValueError(
            f"page_number {page_number} is out of range 1-{total}"
        )
    rect = doc[page_number - 1].rect
    doc.close()
    return float(rect.width), float(rect.height), total


# ── Coordinate validation ─────────────────────────────────────────────────────

def validate_position(x: float, y: float, page_width: float, page_height: float) -> None:
    """Raise ValueError if (x, y) falls outside the printable page area."""
    _EDGE = 5.0  # minimum distance from page edge
    if not (0 <= x <= page_width - _EDGE):
        raise ValueError(
            f"x={x} is outside page width range [0, {page_width - _EDGE:.1f}]"
        )
    if not (0 <= y <= page_height - _EDGE):
        raise ValueError(
            f"y={y} is outside page height range [0, {page_height - _EDGE:.1f}]"
        )


# ── Signature application ─────────────────────────────────────────────────────

def apply_typed_signature(
    source: Path,
    dest: Path,
    text: str,
    x: float,
    y: float,
    page_number: int,
) -> None:
    """Insert a typed text signature into the PDF at (x, y) on the given page."""
    doc = fitz.open(str(source))
    page = doc[page_number - 1]
    page.insert_text(
        (x, y),
        text,
        fontname=_SIG_FONT,
        fontsize=_SIG_FONT_SIZE,
        color=_SIG_COLOR,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest))
    doc.close()


def apply_drawn_signature(
    source: Path,
    dest: Path,
    image_bytes: bytes,
    x: float,
    y: float,
    page_number: int,
) -> None:
    """Insert a drawn (image) signature into the PDF at (x, y) on the given page."""
    doc = fitz.open(str(source))
    page = doc[page_number - 1]
    rect = fitz.Rect(x, y, x + _DRAWN_WIDTH, y + _DRAWN_HEIGHT)
    page.insert_image(rect, stream=image_bytes)
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest))
    doc.close()


# ── Image storage ─────────────────────────────────────────────────────────────

def save_signature_image(document_id: uuid.UUID, image_base64: str) -> str:
    """
    Decode and save a base64 PNG signature image to disk.
    Returns the relative path stored in the DB.
    """
    image_bytes = base64.b64decode(image_base64)
    # Validate it's a readable image (fitz raises if corrupt)
    pix = fitz.Pixmap(image_bytes)
    pix = None  # free immediately

    doc_dir = make_document_dir(str(document_id))
    img_name = f"sig_{uuid.uuid4().hex}.png"
    img_path = doc_dir / img_name
    img_path.write_bytes(image_bytes)
    return f"{document_id}/{img_name}"
