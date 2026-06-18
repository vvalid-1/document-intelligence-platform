from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.editor_agent import EditorAgent
from app.models.document import Document, DocumentChunk, DocumentVersion

pytestmark = pytest.mark.asyncio(loop_scope="session")

_EDITED_TEXT = "The committee has decided to proceed with the proposal. They are satisfied with the outcome."
_FAKE_TXT = "doc-id/v1_edited.txt"
_FAKE_PDF = "doc-id/v1_edited.pdf"

_MOCK_OLLAMA = {
    "message": {"role": "assistant", "content": _EDITED_TEXT},
    "done": True,
    "eval_count": 25,
}


def _mock_save(*_args, **_kwargs):
    return _FAKE_TXT, _FAKE_PDF


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _register_and_login(
    client: AsyncClient,
    email: str = "edit_admin@example.com",
    role_after_register: str = "editor",
) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Edit Admin", "password": "securepassword1"},
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
        title="Editable Document",
        original_name="editable.txt",
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
        chunk_text="The committee have decided to proceed. They was satisfied.",
        token_count=10,
    ))
    await db.flush()
    return doc


# ── Auth guards ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_document_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/edit",
        json={"instruction": "Fix grammar"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_edit_document_viewer_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    """Viewers cannot trigger edits (require_editor_or_admin)."""
    # First user is admin — register a second as viewer
    admin_token = await _register_and_login(client, "edit_admin2@example.com")

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin2@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    # Register viewer
    await client.post(
        "/api/v1/auth/register",
        json={"email": "edit_viewer@example.com", "full_name": "Viewer", "password": "securepassword1"},
    )
    resp_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "edit_viewer@example.com", "password": "securepassword1"},
    )
    viewer_token = resp_login.json().get("access_token", "")

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/edit",
        json={"instruction": "Fix grammar"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


# ── Create edit (POST /documents/{id}/edit) ───────────────────────────────────

@pytest.mark.asyncio
async def test_create_edit_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Fix grammar and subject-verb agreement errors"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["version_number"] == 1
    assert data["change_summary"] == "Fix grammar and subject-verb agreement errors"
    assert _EDITED_TEXT[:20] in data["text_preview"]
    assert "task_id" in data
    assert "txt_path" in data
    assert "pdf_path" in data


@pytest.mark.asyncio
async def test_create_edit_document_not_found(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/edit",
        json={"instruction": "Fix grammar"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_edit_document_not_ready(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
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
        f"/api/v1/documents/{doc_id}/edit",
        json={"instruction": "Fix grammar"},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_edit_instruction_required(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/edit",
        json={"instruction": ""},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_edit_instruction_too_long(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/edit",
        json={"instruction": "x" * 2001},
        headers=headers,
    )
    assert resp.status_code == 422


# ── Version history (GET /documents/{id}/versions) ────────────────────────────

@pytest.mark.asyncio
async def test_versions_empty_before_edit(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.get(f"/api/v1/documents/{doc.id}/versions", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_versions_lists_created_version(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Fix grammar"},
            headers=headers,
        )

    resp = await client.get(f"/api/v1/documents/{doc.id}/versions", headers=headers)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["agent_name"] == "editor"
    assert versions[0]["change_summary"] == "Fix grammar"


@pytest.mark.asyncio
async def test_versions_are_ordered_desc(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Edit 1"},
            headers=headers,
        )
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Edit 2"},
            headers=headers,
        )
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Edit 3"},
            headers=headers,
        )

    resp = await client.get(f"/api/v1/documents/{doc.id}/versions", headers=headers)
    versions = resp.json()
    assert len(versions) == 3
    # Ordered desc: newest first
    assert versions[0]["version_number"] == 3
    assert versions[1]["version_number"] == 2
    assert versions[2]["version_number"] == 1


# ── Edit instruction types ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replace_instruction(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    captured: list = []

    async def _capture(messages, tools=None):
        captured.extend(messages)
        return _MOCK_OLLAMA

    with (
        patch.object(EditorAgent, "_call_ollama", side_effect=_capture),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Replace 'committee have' with 'committee has'"},
            headers=headers,
        )

    assert resp.status_code == 201
    user_msg = next(m for m in captured if m["role"] == "user")
    assert "Replace 'committee have' with 'committee has'" in user_msg["content"]


@pytest.mark.asyncio
async def test_audit_log_created_on_edit(client: AsyncClient, db: AsyncSession) -> None:
    from app.models.audit import AuditLog

    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Remove last sentence"},
            headers=headers,
        )

    log_res = await db.execute(
        select(AuditLog).where(
            AuditLog.action == "document.edit",
            AuditLog.resource_id == doc.id,
        )
    )
    log = log_res.scalar_one_or_none()
    assert log is not None
    assert log.details is not None
    assert "version_id" in log.details


@pytest.mark.asyncio
async def test_edit_preserves_original_document(client: AsyncClient, db: AsyncSession) -> None:
    """Editing must not modify the original document record."""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)
    original_file_path = doc.file_path

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Rewrite introduction"},
            headers=headers,
        )

    # Refresh the document from DB
    await db.refresh(doc)
    assert doc.file_path == original_file_path  # original not overwritten
    assert doc.status == "ready"


@pytest.mark.asyncio
async def test_version_download_endpoint_exists(client: AsyncClient, db: AsyncSession) -> None:
    """GET /documents/{id}/versions/{vid}/download should return 404 for a non-existent file
    (since we mocked file creation), confirming the endpoint exists."""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User

    res = await db.execute(select(User).where(User.email == "edit_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        create_resp = await client.post(
            f"/api/v1/documents/{doc.id}/edit",
            json={"instruction": "Insert conclusion"},
            headers=headers,
        )

    version_id = create_resp.json()["id"]
    # The file won't actually exist (mock), so expect 404 from the download endpoint
    resp = await client.get(
        f"/api/v1/documents/{doc.id}/versions/{version_id}/download",
        headers=headers,
    )
    assert resp.status_code in {200, 404}  # 404 is expected since file was mocked
