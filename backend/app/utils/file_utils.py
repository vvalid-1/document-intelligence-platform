from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# Extension → (allowed mime types, magic bytes)
_ALLOWED: dict[str, tuple[set[str], bytes]] = {
    ".pdf": ({"application/pdf", "application/x-pdf"}, b"%PDF"),
    ".docx": (
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
        b"PK\x03\x04",
    ),
    ".txt": ({"text/plain"}, b""),  # no magic bytes for txt
}


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower()


async def validate_upload(file: UploadFile) -> str:
    """Validate file type, magic bytes, and size. Returns the sanitized extension."""
    ext = _ext(file.filename or "")
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_FILE_TYPE: allowed extensions are {list(_ALLOWED)}",
        )

    # Read the first 8 bytes for magic byte check without consuming the stream
    header = await file.read(8)
    await file.seek(0)

    magic = _ALLOWED[ext][1]
    if magic and not header.startswith(magic):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_FILE_MAGIC: file header does not match declared type",
        )

    # Validate size by reading full content length
    content = await file.read()
    await file.seek(0)
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"FILE_TOO_LARGE: max {settings.MAX_FILE_SIZE_MB} MB",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPTY_FILE",
        )

    return ext


def resolve_upload_path(relative_path: str) -> Path:
    """Resolve a relative path (stored in DB) to an absolute path on disk."""
    base = Path(settings.UPLOAD_DIR)
    full = (base / relative_path).resolve()
    # Guard against path traversal
    if not str(full).startswith(str(base.resolve())):
        raise ValueError("Path traversal detected")
    return full


def make_document_dir(document_id: str) -> Path:
    doc_dir = Path(settings.UPLOAD_DIR) / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    return doc_dir
