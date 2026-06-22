from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# Extension → (allowed mime types, magic bytes at offset 0)
# MP4 is special: magic is "ftyp" at offset 4, handled separately below.
_ALLOWED: dict[str, tuple[set[str], bytes]] = {
    ".pdf": ({"application/pdf", "application/x-pdf"}, b"%PDF"),
    ".docx": (
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
        b"PK\x03\x04",
    ),
    ".txt": ({"text/plain"}, b""),
    ".jpg": ({"image/jpeg"}, b"\xff\xd8\xff"),
    ".jpeg": ({"image/jpeg"}, b"\xff\xd8\xff"),
    ".png": ({"image/png"}, b"\x89PNG"),
    # MP3: ID3 header (most common) or raw MPEG sync word
    ".mp3": ({"audio/mpeg", "audio/mp3"}, b""),
    # WAV: RIFF container
    ".wav": ({"audio/wav", "audio/x-wav", "audio/wave"}, b"RIFF"),
    # MP4: variable-length box; "ftyp" is at bytes 4-7 (checked separately)
    ".mp4": ({"video/mp4", "video/mpeg"}, b""),
}

_MEDIA_EXTENSIONS = {".mp3", ".wav", ".mp4"}


def _ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def _check_mp3_magic(header: bytes) -> bool:
    """Accept ID3 tag or raw MPEG sync word."""
    return (
        header[:3] == b"ID3"
        or header[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"}
    )


def _check_mp4_magic(header: bytes) -> bool:
    """MP4 ftyp box: bytes 4-7 must be 'ftyp'."""
    return len(header) >= 8 and header[4:8] == b"ftyp"


async def validate_upload(file: UploadFile) -> str:
    """Validate file type, magic bytes, and size. Returns the sanitized extension."""
    ext = _ext(file.filename or "")
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_FILE_TYPE: allowed extensions are {list(_ALLOWED)}",
        )

    header = await file.read(8)
    await file.seek(0)

    # Per-format magic byte checks
    if ext == ".mp3":
        if not _check_mp3_magic(header):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_FILE_MAGIC: file header does not match declared type",
            )
    elif ext == ".mp4":
        if not _check_mp4_magic(header):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_FILE_MAGIC: file header does not match declared type",
            )
    else:
        magic = _ALLOWED[ext][1]
        if magic and not header.startswith(magic):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_FILE_MAGIC: file header does not match declared type",
            )

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
