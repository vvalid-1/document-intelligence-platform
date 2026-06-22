from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.folder import Folder

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Folder User", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_doc(db: AsyncSession, owner_id: uuid.UUID, folder_id: uuid.UUID | None = None) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="Folder Test Doc",
        original_name="test.pdf",
        file_path=f"{uuid.uuid4()}/original.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        status="ready",
        chunk_count=1,
        folder_id=folder_id,
    )
    db.add(doc)
    await db.flush()
    return doc


async def _make_folder(db: AsyncSession, owner_id: uuid.UUID, name: str) -> Folder:
    folder = Folder(id=uuid.uuid4(), owner_id=owner_id, name=name)
    db.add(folder)
    await db.flush()
    return folder


@pytest.mark.asyncio
async def test_create_folder(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_create@example.com")

    resp = await client.post(
        "/api/v1/folders",
        json={"name": "My Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Project"
    assert body["doc_count"] == 0
    assert "id" in body


@pytest.mark.asyncio
async def test_create_duplicate_folder_name_rejected(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_dup@example.com")

    await client.post(
        "/api/v1/folders",
        json={"name": "Reports"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        "/api/v1/folders",
        json={"name": "Reports"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_folders_with_doc_count(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_list@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_list@example.com"))).scalar_one()

    folder = await _make_folder(db, user.id, "Scholarship")
    await _make_doc(db, user.id, folder_id=folder.id)
    await _make_doc(db, user.id, folder_id=folder.id)
    await _make_doc(db, user.id, folder_id=None)

    resp = await client.get(
        "/api/v1/folders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    match = next((f for f in items if f["id"] == str(folder.id)), None)
    assert match is not None
    assert match["doc_count"] == 2


@pytest.mark.asyncio
async def test_rename_folder(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_rename@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_rename@example.com"))).scalar_one()
    folder = await _make_folder(db, user.id, "Old Name")

    resp = await client.patch(
        f"/api/v1/folders/{folder.id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_folder_unassigns_docs(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_delete@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_delete@example.com"))).scalar_one()
    folder = await _make_folder(db, user.id, "To Delete")
    doc = await _make_doc(db, user.id, folder_id=folder.id)

    resp = await client.delete(
        f"/api/v1/folders/{folder.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    await db.refresh(doc)
    assert doc.folder_id is None


@pytest.mark.asyncio
async def test_move_document_to_folder(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_move@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_move@example.com"))).scalar_one()
    folder = await _make_folder(db, user.id, "Target Folder")
    doc = await _make_doc(db, user.id)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/move",
        json={"folder_id": str(folder.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["folder_id"] == str(folder.id)


@pytest.mark.asyncio
async def test_filter_documents_by_folder(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_filter@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_filter@example.com"))).scalar_one()
    folder = await _make_folder(db, user.id, "Filter Target")
    await _make_doc(db, user.id, folder_id=folder.id)
    await _make_doc(db, user.id, folder_id=folder.id)
    await _make_doc(db, user.id, folder_id=None)

    resp = await client.get(
        f"/api/v1/documents?folder_id={folder.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["folder_id"] == str(folder.id)


@pytest.mark.asyncio
async def test_bulk_move_documents(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "folder_bulk@example.com")

    from app.models.user import User
    from sqlalchemy import select
    user = (await db.execute(select(User).where(User.email == "folder_bulk@example.com"))).scalar_one()
    folder = await _make_folder(db, user.id, "Bulk Target")
    doc1 = await _make_doc(db, user.id)
    doc2 = await _make_doc(db, user.id)

    resp = await client.post(
        "/api/v1/documents/bulk/move",
        json={"ids": [str(doc1.id), str(doc2.id)], "folder_id": str(folder.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    await db.refresh(doc1)
    await db.refresh(doc2)
    assert doc1.folder_id == folder.id
    assert doc2.folder_id == folder.id
