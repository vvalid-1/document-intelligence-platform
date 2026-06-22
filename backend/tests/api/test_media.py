from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ── Magic byte helpers ────────────────────────────────────────────────────────

def _mp3_bytes() -> bytes:
    """Minimal MP3 file with ID3 header magic bytes."""
    return b"ID3" + b"\x00" * 100

def _wav_bytes() -> bytes:
    """Minimal WAV file with RIFF magic bytes."""
    return b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 50

def _mp4_bytes() -> bytes:
    """Minimal MP4 file with ftyp box at offset 4."""
    # box-size (4 bytes) + "ftyp" + compatible brand
    return b"\x00\x00\x00\x20" + b"ftyp" + b"mp42" + b"\x00" * 50

# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Media User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_media_doc(
    db: AsyncSession,
    owner_id: uuid.UUID,
    mime_type: str = "audio/mpeg",
    status: str = "ready",
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="Test Recording",
        original_name="recording.mp3",
        file_path=f"{uuid.uuid4()}/original.mp3",
        file_size_bytes=50000,
        mime_type=mime_type,
        status=status,
        chunk_count=3,
        media_duration_seconds=120.5,
    )
    db.add(doc)
    await db.flush()
    return doc


async def _make_media_version(
    db: AsyncSession,
    doc_id: uuid.UUID,
    owner_id: uuid.UUID,
    transcript: str = "Hello world this is a test transcript.",
) -> DocumentVersion:
    version = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_number=1,
        created_by=owner_id,
        file_path=f"{doc_id}/v1_summary.pdf",
        change_summary="Media analysis: transcript + AI summary",
        agent_name="media_analysis",
        version_metadata={
            "transcript": transcript,
            "summary": "Test summary.",
            "key_topics": ["Topic A", "Topic B"],
            "action_items": ["Do task X"],
            "important_dates": ["2026-03-15 — deadline"],
            "important_numbers": ["$1M budget"],
            "txt_path": f"{doc_id}/v1_transcript.txt",
            "pdf_path": f"{doc_id}/v1_summary.pdf",
            "duration_seconds": 120.5,
            "language": "en",
            "model": "qwen2.5:3b",
        },
    )
    db.add(version)
    await db.flush()
    return version

# ── Upload tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_mp3_accepted(client: AsyncClient, db: AsyncSession) -> None:
    """MP3 with valid ID3 magic bytes should be accepted (202)."""
    token = await _register_and_login(client, "media_mp3@example.com")

    with (
        patch("app.api.v1.documents._process_document"),
        patch("app.api.v1.documents.transcribe_audio"),
    ):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("meeting.mp3", io.BytesIO(_mp3_bytes()), "audio/mpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert "id" in data

    # Verify mime_type stored correctly
    doc_id = uuid.UUID(data["id"])
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    assert doc is not None
    assert doc.mime_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_upload_wav_accepted(client: AsyncClient, db: AsyncSession) -> None:
    """WAV with valid RIFF magic bytes should be accepted (202)."""
    token = await _register_and_login(client, "media_wav@example.com")

    with patch("app.api.v1.documents._process_document"):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("interview.wav", io.BytesIO(_wav_bytes()), "audio/wav")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    assert resp.json()["id"]


@pytest.mark.asyncio
async def test_upload_mp4_accepted(client: AsyncClient, db: AsyncSession) -> None:
    """MP4 with valid ftyp magic bytes should be accepted (202)."""
    token = await _register_and_login(client, "media_mp4@example.com")

    with patch("app.api.v1.documents._process_document"):
        resp = await client.post(
            "/api/v1/documents",
            files={"file": ("video.mp4", io.BytesIO(_mp4_bytes()), "video/mp4")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_invalid_extension_rejected(client: AsyncClient) -> None:
    """Unsupported extension (.avi) should be rejected with 400."""
    token = await _register_and_login(client, "media_avi@example.com")

    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("video.avi", io.BytesIO(b"\x00" * 100), "video/avi")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "INVALID_FILE_TYPE" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_magic_bytes_rejected(client: AsyncClient) -> None:
    """MP3 extension with PDF magic bytes should be rejected with 400."""
    token = await _register_and_login(client, "media_badmagic@example.com")

    resp = await client.post(
        "/api/v1/documents",
        files={"file": ("fake.mp3", io.BytesIO(b"%PDF-1.4" + b"\x00" * 50), "audio/mpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "INVALID_FILE_MAGIC" in resp.json()["detail"]

# ── Media analysis endpoint tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_media_analysis_not_found_returns_404(
    client: AsyncClient, db: AsyncSession
) -> None:
    """GET /media-analysis on a media doc with no completed version returns 404."""
    token = await _register_and_login(client, "media_noversion@example.com")

    from app.models.user import User
    user = (
        await db.execute(select(User).where(User.email == "media_noversion@example.com"))
    ).scalar_one()
    doc = await _make_media_doc(db, user.id)

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/media-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_media_analysis_returns_correct_schema(
    client: AsyncClient, db: AsyncSession
) -> None:
    """GET /media-analysis returns transcript, summary, topics, etc."""
    token = await _register_and_login(client, "media_schema@example.com")

    from app.models.user import User
    user = (
        await db.execute(select(User).where(User.email == "media_schema@example.com"))
    ).scalar_one()
    doc = await _make_media_doc(db, user.id)
    await _make_media_version(db, doc.id, user.id, transcript="This is the full transcript.")

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/media-analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "This is the full transcript."
    assert data["summary"] == "Test summary."
    assert isinstance(data["key_topics"], list)
    assert isinstance(data["action_items"], list)
    assert isinstance(data["important_dates"], list)
    assert isinstance(data["important_numbers"], list)
    assert data["language"] == "en"
    assert data["duration_seconds"] == pytest.approx(120.5)


@pytest.mark.asyncio
async def test_stats_includes_media_analyses_count(
    client: AsyncClient, db: AsyncSession
) -> None:
    """GET /documents/stats returns media_analyses integer key."""
    token = await _register_and_login(client, "media_stats@example.com")

    resp = await client.get(
        "/api/v1/documents/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "media_analyses" in data
    assert isinstance(data["media_analyses"], int)
