from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Bulk User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_docs(db: AsyncSession, owner_id: uuid.UUID, count: int = 3) -> list[Document]:
    docs = []
    for _ in range(count):
        doc = Document(
            id=uuid.uuid4(),
            owner_id=owner_id,
            title="Bulk Doc",
            original_name="bulk.pdf",
            file_path=f"{uuid.uuid4()}/original.pdf",
            file_size_bytes=500,
            mime_type="application/pdf",
            status="ready",
            chunk_count=1,
        )
        db.add(doc)
        docs.append(doc)
    await db.flush()
    return docs


@pytest.mark.asyncio
async def test_bulk_archive(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "bulk_archive@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "bulk_archive@example.com"))).scalar_one()
    docs = await _make_docs(db, user.id, 3)
    ids = [str(d.id) for d in docs]

    resp = await client.post(
        "/api/v1/documents/bulk/archive",
        json={"ids": ids},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    for doc in docs:
        await db.refresh(doc)
        assert doc.is_archived is True


@pytest.mark.asyncio
async def test_bulk_restore(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "bulk_restore@example.com")

    from app.models.user import User
    from sqlalchemy import select, update
    user = (await db.execute(select(User).where(User.email == "bulk_restore@example.com"))).scalar_one()
    docs = await _make_docs(db, user.id, 2)
    ids = [str(d.id) for d in docs]

    # Archive them first
    await db.execute(
        update(Document).where(Document.id.in_([d.id for d in docs])).values(is_archived=True)
    )
    await db.flush()

    resp = await client.post(
        "/api/v1/documents/bulk/restore",
        json={"ids": ids},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    for doc in docs:
        await db.refresh(doc)
        assert doc.is_archived is False


@pytest.mark.asyncio
async def test_bulk_trash(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "bulk_trash@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "bulk_trash@example.com"))).scalar_one()
    docs = await _make_docs(db, user.id, 2)
    ids = [str(d.id) for d in docs]

    resp = await client.post(
        "/api/v1/documents/bulk/trash",
        json={"ids": ids},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    for doc in docs:
        await db.refresh(doc)
        assert doc.is_deleted is True


@pytest.mark.asyncio
async def test_bulk_favorite(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "bulk_fav@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "bulk_fav@example.com"))).scalar_one()
    docs = await _make_docs(db, user.id, 2)
    ids = [str(d.id) for d in docs]

    resp = await client.post(
        "/api/v1/documents/bulk/favorite",
        json={"ids": ids, "value": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    for doc in docs:
        await db.refresh(doc)
        assert doc.is_favorite is True


@pytest.mark.asyncio
async def test_bulk_empty_ids_rejected(client: AsyncClient) -> None:
    token = await _register_and_login(client, "bulk_empty@example.com")

    resp = await client.post(
        "/api/v1/documents/bulk/archive",
        json={"ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/documents/bulk/archive",
        json={"ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 403
