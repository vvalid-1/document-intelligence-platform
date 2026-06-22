from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

pytestmark = pytest.mark.asyncio(loop_scope="session")

_FAKE_EMBEDDING = [[0.1] * 10]


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Archive User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_ready_doc(db: AsyncSession, owner_id: uuid.UUID, archived: bool = False) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="Test Document",
        original_name="test.pdf",
        file_path=f"{uuid.uuid4()}/original.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        status="ready",
        chunk_count=2,
        is_archived=archived,
    )
    db.add(doc)
    await db.flush()
    return doc


# ── Archive ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "archive_basic@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "archive_basic@example.com"))).scalar_one()

    doc = await _make_ready_doc(db, user.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_archived"] is True
    assert body["archived_at"] is not None


@pytest.mark.asyncio
async def test_archive_already_archived_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "archive_409@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "archive_409@example.com"))).scalar_one()

    doc = await _make_ready_doc(db, user.id, archived=True)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# ── Restore ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restore_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "restore_basic@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "restore_basic@example.com"))).scalar_one()

    doc = await _make_ready_doc(db, user.id, archived=True)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_archived"] is False
    assert body["archived_at"] is None


@pytest.mark.asyncio
async def test_restore_not_archived_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "restore_409@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "restore_409@example.com"))).scalar_one()

    doc = await _make_ready_doc(db, user.id, archived=False)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


# ── List filtering ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archived_doc_excluded_from_normal_list(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "archive_list@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "archive_list@example.com"))).scalar_one()

    await _make_ready_doc(db, user.id, archived=False)
    await _make_ready_doc(db, user.id, archived=True)

    resp = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert not body["items"][0]["is_archived"]


@pytest.mark.asyncio
async def test_archived_doc_in_archived_list(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "archive_archived_list@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "archive_archived_list@example.com"))).scalar_one()

    await _make_ready_doc(db, user.id, archived=False)
    await _make_ready_doc(db, user.id, archived=True)

    resp = await client.get(
        "/api/v1/documents?archived=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_archived"] is True


# ── Search exclusion ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archived_doc_excluded_from_search(client: AsyncClient, db: AsyncSession) -> None:
    from unittest.mock import MagicMock, patch

    token = await _register_and_login(client, "archive_search@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "archive_search@example.com"))).scalar_one()

    archived_doc = await _make_ready_doc(db, user.id, archived=True)
    archived_id = str(archived_doc.id)

    chroma_result = {
        "documents": [["Some archived content."]],
        "metadatas": [[
            {"document_id": archived_id, "document_title": "Test Document", "chunk_index": 0, "page_number": 1},
        ]],
        "distances": [[0.05]],
    }
    col = MagicMock()
    col.count.return_value = 1
    col.query.return_value = chroma_result

    with (
        patch("app.api.v1.search.embed_texts", return_value=_FAKE_EMBEDDING),
        patch("app.api.v1.search.get_document_collection", return_value=col),
    ):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "archived content"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hits"] == 0
    assert body["total_documents"] == 0


# ── Auth guard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_requires_auth(client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await client.post(f"/api/v1/documents/{fake_id}/archive")
    assert resp.status_code == 403
