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
        json={"email": email, "full_name": "Fav User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_ready_doc(db: AsyncSession, owner_id: uuid.UUID, favorite: bool = False) -> Document:
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
        is_favorite=favorite,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_favorite_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "fav_basic@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "fav_basic@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorite"] is True


@pytest.mark.asyncio
async def test_unfavorite_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "fav_unstar@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "fav_unstar@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id, favorite=True)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/unfavorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_favorite"] is False


@pytest.mark.asyncio
async def test_favorite_already_starred_returns_409(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "fav_409@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "fav_409@example.com"))).scalar_one()
    doc = await _make_ready_doc(db, user.id, favorite=True)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/favorite",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_favorite_filter_returns_only_starred(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "fav_filter@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "fav_filter@example.com"))).scalar_one()
    await _make_ready_doc(db, user.id, favorite=False)
    await _make_ready_doc(db, user.id, favorite=True)

    resp = await client.get(
        "/api/v1/documents?favorite=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_favorite"] is True


@pytest.mark.asyncio
async def test_stats_includes_favorites_count(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "fav_stats@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "fav_stats@example.com"))).scalar_one()
    await _make_ready_doc(db, user.id, favorite=True)
    await _make_ready_doc(db, user.id, favorite=True)
    await _make_ready_doc(db, user.id, favorite=False)

    resp = await client.get(
        "/api/v1/documents/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "favorites" in body
    assert body["favorites"] == 2


@pytest.mark.asyncio
async def test_favorite_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/favorite")
    assert resp.status_code == 403
