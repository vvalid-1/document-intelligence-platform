from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.translation_agent import TranslationAgent
from app.models.document import Document, DocumentChunk

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TRANSLATED_FR = "Le comité a décidé de procéder avec la proposition. Ils sont satisfaits du résultat."
_FAKE_TXT = "doc-id/v1_translated_fr.txt"
_FAKE_PDF = "doc-id/v1_translated_fr.pdf"

_MOCK_OLLAMA = {
    "message": {"role": "assistant", "content": _TRANSLATED_FR},
    "done": True,
    "eval_count": 30,
}


def _mock_save(*_args, **_kwargs):
    return _FAKE_TXT, _FAKE_PDF


async def _register_and_login(
    client: AsyncClient,
    email: str = "trans_admin@example.com",
) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Trans Admin", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_ready_doc(db: AsyncSession, owner_id: uuid.UUID) -> Document:
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=owner_id,
        title="Translatable Document",
        original_name="doc.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=200,
        mime_type="text/plain",
        status="ready",
        chunk_count=1,
    )
    db.add(doc)
    await db.flush()
    db.add(DocumentChunk(
        document_id=doc_id,
        chroma_chunk_id=f"{doc_id}_0",
        chunk_index=0,
        chunk_text="The committee has decided to proceed with the proposal. They are satisfied.",
        token_count=12,
    ))
    await db.flush()
    return doc


# ── Auth guards ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/translate",
        json={"target_language": "fr"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_translate_viewer_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    admin_token = await _register_and_login(client, "trans_admin2@example.com")

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin2@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    await client.post(
        "/api/v1/auth/register",
        json={"email": "trans_viewer@example.com", "full_name": "Viewer", "password": "securepassword1"},
    )
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "trans_viewer@example.com", "password": "securepassword1"},
    )
    viewer_token = resp_login.json().get("access_token", "")

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/translate",
        json={"target_language": "fr"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_invalid_language(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/translate",
        json={"target_language": "de"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_translate_document_not_found(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/translate",
        json={"target_language": "fr"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_translate_document_not_ready(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        owner_id=admin.id,
        title="Processing Doc",
        original_name="proc.pdf",
        file_path=f"{doc_id}/original.pdf",
        file_size_bytes=500,
        mime_type="application/pdf",
        status="processing",
    )
    db.add(doc)
    await db.flush()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/translate",
        json={"target_language": "fr"},
        headers=headers,
    )
    assert resp.status_code == 409


# ── Success cases ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_to_french_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(TranslationAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.translation_agent.save_version_files", side_effect=_mock_save),
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/translate",
            json={"target_language": "fr"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["version_number"] == 1
    assert data["target_language"] == "fr"
    assert data["language_name"] == "French"
    assert data["change_summary"] == "Translated to French"
    assert _TRANSLATED_FR[:20] in data["text_preview"]
    assert "txt_path" in data
    assert "pdf_path" in data
    assert "task_id" in data


@pytest.mark.asyncio
async def test_translate_to_arabic_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    arabic_text = "قرر اللجنة المضي قدما في المقترح."
    mock_ar = {"message": {"role": "assistant", "content": arabic_text}, "done": True, "eval_count": 15}

    with (
        patch.object(TranslationAgent, "_call_ollama", new_callable=AsyncMock, return_value=mock_ar),
        patch("app.agents.translation_agent.save_version_files", side_effect=_mock_save),
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/translate",
            json={"target_language": "ar"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["target_language"] == "ar"
    assert data["language_name"] == "Arabic"
    assert data["change_summary"] == "Translated to Arabic"


@pytest.mark.asyncio
async def test_translate_preserves_original_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)
    original_path = doc.file_path

    with (
        patch.object(TranslationAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.translation_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/translate",
            json={"target_language": "fr"},
            headers=headers,
        )

    await db.refresh(doc)
    assert doc.file_path == original_path
    assert doc.status == "ready"


@pytest.mark.asyncio
async def test_translate_audit_log_created(client: AsyncClient, db: AsyncSession) -> None:
    from app.models.audit import AuditLog

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "trans_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(TranslationAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.translation_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/translate",
            json={"target_language": "fr"},
            headers=headers,
        )

    log_res = await db.execute(
        select(AuditLog).where(
            AuditLog.action == "document.translate",
            AuditLog.resource_id == doc.id,
        )
    )
    log = log_res.scalar_one_or_none()
    assert log is not None
    assert log.details is not None
    assert log.details["target_language"] == "fr"
    assert log.details["language_name"] == "French"
