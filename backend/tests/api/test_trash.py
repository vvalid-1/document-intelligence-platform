from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _register_and_login(client: AsyncClient, email: str, role: str = "admin") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Trash User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_ready_doc(db: AsyncSession, owner_id: uuid.UUID, is_deleted: bool = False) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="Trash Test Doc",
        original_name="test.pdf",
        file_path=f"{uuid.uuid4()}/original.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        status="ready",
        chunk_count=2,
        is_deleted=is_deleted,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_move_to_trash(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_basic@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_basic@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id)

    resp = await client.delete(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    await db.refresh(doc)
    assert doc.is_deleted is True
    assert doc.deleted_at is not None


@pytest.mark.asyncio
async def test_trashed_doc_excluded_from_normal_list(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_list@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_list@example.com"))).scalar_one()
    await _make_ready_doc(db, user.id, is_deleted=False)
    await _make_ready_doc(db, user.id, is_deleted=True)

    resp = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_trashed_doc_appears_in_trash_list(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_trash_list@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_trash_list@example.com"))).scalar_one()
    await _make_ready_doc(db, user.id, is_deleted=False)
    await _make_ready_doc(db, user.id, is_deleted=True)

    resp = await client.get(
        "/api/v1/documents?trashed=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_deleted"] is True


@pytest.mark.asyncio
async def test_restore_from_trash(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_restore@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_restore@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id, is_deleted=True)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/untrash",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_deleted"] is False
    assert body["deleted_at"] is None


@pytest.mark.asyncio
async def test_permanent_delete_admin_only(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_perm@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_perm@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id, is_deleted=True)

    col = MagicMock()
    col.delete.return_value = None

    with (
        patch("app.api.v1.documents.get_document_collection", return_value=col),
        patch("app.api.v1.documents.delete_document_chunks", return_value=None),
    ):
        resp = await client.delete(
            f"/api/v1/documents/{doc.id}/permanent",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 204

    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(Document).where(Document.id == doc.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_stats_includes_trash_count(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_stats@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "trash_stats@example.com"))).scalar_one()
    await _make_ready_doc(db, user.id, is_deleted=True)
    await _make_ready_doc(db, user.id, is_deleted=True)
    await _make_ready_doc(db, user.id, is_deleted=False)

    resp = await client.get(
        "/api/v1/documents/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "trash" in body
    assert body["trash"] == 2


@pytest.mark.asyncio
async def test_restore_from_nonexistent_trash_returns_404(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "trash_404@example.com")

    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/untrash",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
