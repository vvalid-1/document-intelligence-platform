from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentSession, AgentMessage, AgentTask
from app.models.document import Document, DocumentChunk

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ── Shared mock helpers ───────────────────────────────────────────────────────

_MOCK_ANSWER = "Based on the context [Source 1], the answer is clear."
# Raw format returned by _retrieve_chunks (has 'text'/'similarity', NOT 'excerpt'/'similarity_score')
_MOCK_CHUNKS = [
    {
        "text": "Relevant passage from the document about the topic.",
        "document_id": str(uuid.uuid4()),
        "document_title": "Test Document",
        "page_number": 1,
        "chunk_index": 0,
        "similarity": 0.92,
    }
]


async def _register_and_login(client: AsyncClient) -> str:
    """Register the first user (admin) and return a Bearer token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": "chat_admin@example.com", "full_name": "Chat Admin", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "chat_admin@example.com", "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


# ── Session tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/chat/sessions", json={"name": "My Session"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_session_success(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"name": "Test Session"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_name"] == "Test Session"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_session_no_name(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["session_name"] is None


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/chat/sessions", json={"name": "S1"}, headers=headers)
    await client.post("/api/v1/chat/sessions", json={"name": "S2"}, headers=headers)
    resp = await client.get("/api/v1/chat/sessions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_get_session_detail(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={"name": "Detail"}, headers=headers)
    sid = create.json()["id"]
    resp = await client.get(f"/api/v1/chat/sessions/{sid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_get_session_other_user_404(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)

    # Create a different user and a session owned by them
    from app.models.user import User
    from app.core.security import hash_password
    other_user = User(
        email="other_user_chat@example.com",
        full_name="Other User",
        hashed_password=hash_password("securepassword1"),
        role="viewer",
        is_active=True,
    )
    db.add(other_user)
    await db.flush()
    other_session = AgentSession(user_id=other_user.id, is_active=True)
    db.add(other_session)
    await db.flush()

    resp = await client.get(
        f"/api/v1/chat/sessions/{other_session.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_close_session(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={"name": "Close me"}, headers=headers)
    sid = create.json()["id"]
    resp = await client.delete(f"/api/v1/chat/sessions/{sid}", headers=headers)
    assert resp.status_code == 204
    detail = await client.get(f"/api/v1/chat/sessions/{sid}", headers=headers)
    assert detail.json()["is_active"] is False


# ── Q&A message tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_question_returns_answer(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    sid = create.json()["id"]

    with (
        patch(
            "app.agents.rag_agent.RAGAgent._retrieve_chunks",
            new_callable=AsyncMock,
            return_value=_MOCK_CHUNKS,
        ),
        patch(
            "app.agents.base.BaseAgent._call_ollama",
            new_callable=AsyncMock,
            return_value={
                "message": {"role": "assistant", "content": _MOCK_ANSWER},
                "done": True,
                "eval_count": 20,
            },
        ),
    ):
        resp = await client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"question": "What is the document about?"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == _MOCK_ANSWER
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_num"] == 1
    assert "task_id" in data
    assert data["token_count"] == 20


@pytest.mark.asyncio
async def test_ask_question_no_chunks_returns_graceful_response(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    sid = create.json()["id"]

    with patch(
        "app.agents.rag_agent.RAGAgent._retrieve_chunks",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"question": "Anything in the documents?"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "could not find" in data["answer"].lower()
    assert data["sources"] == []


@pytest.mark.asyncio
async def test_ask_on_closed_session_returns_409(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    sid = create.json()["id"]
    await client.delete(f"/api/v1/chat/sessions/{sid}", headers=headers)

    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"question": "Test"},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_messages_persisted_in_session(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    sid = create.json()["id"]

    with (
        patch("app.agents.rag_agent.RAGAgent._retrieve_chunks", new_callable=AsyncMock, return_value=[]),
    ):
        await client.post(
            f"/api/v1/chat/sessions/{sid}/messages",
            json={"question": "Question one?"},
            headers=headers,
        )

    detail = await client.get(f"/api/v1/chat/sessions/{sid}", headers=headers)
    messages = detail.json()["messages"]
    assert len(messages) == 2  # user + assistant
    roles = {m["role"] for m in messages}
    assert roles == {"user", "assistant"}


@pytest.mark.asyncio
async def test_ask_question_invalid_document_id_404(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/v1/chat/sessions", json={}, headers=headers)
    sid = create.json()["id"]

    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"question": "Test", "document_ids": [str(uuid.uuid4())]},
        headers=headers,
    )
    assert resp.status_code == 404


# ── Summarize tests ───────────────────────────────────────────────────────────

async def _make_ready_document(db: AsyncSession, owner_id: uuid.UUID) -> Document:
    doc = Document(
        owner_id=owner_id,
        title="Test Doc",
        original_name="test.txt",
        file_path=f"{uuid.uuid4()}/original.txt",
        file_size_bytes=100,
        mime_type="text/plain",
        status="ready",
        chunk_count=2,
    )
    db.add(doc)
    await db.flush()
    for i in range(2):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                chroma_chunk_id=f"{doc.id}_{i}",
                chunk_index=i,
                chunk_text=f"Chunk {i}: This document discusses important topics in detail.",
                token_count=10,
            )
        )
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_summarize_document_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Find the owner_id by looking up the registered user
    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "chat_admin@example.com"))
    admin_user = res.scalar_one_or_none()
    assert admin_user is not None

    doc = await _make_ready_document(db, admin_user.id)

    with patch(
        "app.agents.base.BaseAgent._call_ollama",
        new_callable=AsyncMock,
        return_value={
            "message": {"role": "assistant", "content": "This document is about testing."},
            "done": True,
            "eval_count": 15,
        },
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/summarize",
            json={"length": "short"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == "This document is about testing."
    assert data["chunk_count"] == 2
    assert data["document_id"] == str(doc.id)
    assert "task_id" in data


@pytest.mark.asyncio
async def test_summarize_document_not_ready_409(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "chat_admin@example.com"))
    admin_user = res.scalar_one_or_none()
    assert admin_user is not None

    doc = Document(
        owner_id=admin_user.id,
        title="Processing Doc",
        original_name="test.pdf",
        file_path=f"{uuid.uuid4()}/original.pdf",
        file_size_bytes=500,
        mime_type="application/pdf",
        status="processing",
    )
    db.add(doc)
    await db.flush()

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/summarize",
        json={"length": "short"},
        headers=headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_summarize_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/summarize", json={})
    assert resp.status_code == 403
