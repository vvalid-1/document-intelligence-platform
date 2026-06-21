from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

pytestmark = pytest.mark.asyncio(loop_scope="session")

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
_JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 20


async def _register_and_login(
    client: AsyncClient,
    email: str = "ocr_admin@example.com",
) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "OCR Admin", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


# ── Extension / magic byte validation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_unsupported_extension_rejected(client: AsyncClient) -> None:
    """GIF files must be rejected regardless of auth state."""
    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("photo.gif", b"GIF89a" + b"\x00" * 20, "image/gif")},
    )
    assert resp.status_code in (400, 403)


@pytest.mark.asyncio
async def test_png_bad_magic_rejected(client: AsyncClient) -> None:
    """A .png file with JPEG header bytes must be rejected."""
    token = await _register_and_login(client, "ocr_badmagic@example.com")
    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("image.png", _JPEG_MAGIC, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "INVALID_FILE_MAGIC" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_jpeg_bad_magic_rejected(client: AsyncClient) -> None:
    """A .jpg file with PNG header bytes must be rejected."""
    token = await _register_and_login(client, "ocr_badmagicjpg@example.com")
    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("photo.jpg", _PNG_MAGIC, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "INVALID_FILE_MAGIC" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_empty_png_rejected(client: AsyncClient) -> None:
    """Empty image files must be rejected."""
    token = await _register_and_login(client, "ocr_empty@example.com")
    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("empty.png", b"", "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (400, 422)


# ── Successful upload acceptance ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_png_upload_accepted(client: AsyncClient) -> None:
    """A PNG with correct magic bytes must be accepted (202)."""
    token = await _register_and_login(client, "ocr_png@example.com")
    with patch("app.api.v1.documents._process_document"):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("scan.png", _PNG_MAGIC, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "processing"
    assert "stream_url" in body


@pytest.mark.asyncio
async def test_jpeg_upload_accepted(client: AsyncClient) -> None:
    """A JPEG with correct magic bytes must be accepted (202)."""
    token = await _register_and_login(client, "ocr_jpeg@example.com")
    with patch("app.api.v1.documents._process_document"):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("photo.jpg", _JPEG_MAGIC, "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 202


# ── OCR extraction function ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_text_image_returns_ocr_text() -> None:
    """extract_text_image calls pytesseract and returns stripped text."""
    from pathlib import Path
    from app.services.processing_service import extract_text_image

    fake_img = MagicMock()
    with (
        patch("app.services.processing_service.Image.open", return_value=fake_img),
        patch("app.services.processing_service.pytesseract.image_to_string", return_value="  Hello OCR  \n") as mock_ocr,
    ):
        result = extract_text_image(Path("/fake/image.png"))

    assert result == "Hello OCR"
    mock_ocr.assert_called_once_with(fake_img, timeout=30)


@pytest.mark.asyncio
async def test_extract_text_image_returns_empty_on_failure() -> None:
    """extract_text_image returns empty string when OCR throws."""
    from pathlib import Path
    from app.services.processing_service import extract_text_image

    with (
        patch("app.services.processing_service.Image.open", side_effect=OSError("bad image")),
    ):
        result = extract_text_image(Path("/fake/corrupt.png"))

    assert result == ""


@pytest.mark.asyncio
async def test_image_mime_stored_correctly(client: AsyncClient, db: AsyncSession) -> None:
    """Uploaded PNG is stored with image/png MIME type in the database."""
    from sqlalchemy import select
    from app.models.document import Document

    token = await _register_and_login(client, "ocr_mimetype@example.com")
    with patch("app.api.v1.documents._process_document"):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("scan.png", _PNG_MAGIC, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 202
    doc_id = uuid.UUID(resp.json()["id"])

    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.mime_type == "image/png"
