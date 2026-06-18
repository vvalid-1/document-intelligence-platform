from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reviewer_agent import ReviewerAgent
from app.models.document import Document, DocumentChunk, DocumentReview

pytestmark = pytest.mark.asyncio(loop_scope="session")

_REVIEW_JSON = {
    "overall_score": 8.0,
    "summary": "The document is clear and mostly well-written.",
    "issues": [
        {
            "type": "grammar",
            "severity": "medium",
            "location": "Paragraph 1",
            "description": "Passive voice overuse.",
            "suggestion": "Use active voice.",
        }
    ],
}

_MOCK_OLLAMA = {
    "message": {"role": "assistant", "content": json.dumps(_REVIEW_JSON)},
    "done": True,
    "eval_count": 60,
}


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str = "review_admin@example.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Review Admin", "password": "securepassword1"},
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
        title="Reviewable Document",
        original_name="doc.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=150,
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
        chunk_text="The committee have decided to proceed with the proposal. They was satisfied.",
        token_count=15,
    ))
    await db.flush()
    return doc


# ── Auth guards ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_review_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/review", json={})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_reviews_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}/reviews")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_review_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}/reviews/{uuid.uuid4()}")
    assert resp.status_code == 403


# ── Create review ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_review_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()

    doc = await _make_ready_doc(db, admin.id)

    with patch.object(
        ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["overall_score"] == 8.0
    assert data["issue_count"] == 1
    assert data["issues"][0]["type"] == "grammar"
    assert data["summary"] == _REVIEW_JSON["summary"]
    assert "task_id" in data


@pytest.mark.asyncio
async def test_create_review_with_focus_areas(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()

    doc = await _make_ready_doc(db, admin.id)

    with patch.object(
        ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA
    ):
        resp = await client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"focus_areas": ["grammar", "spelling"]},
            headers=headers,
        )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_review_document_not_found(client: AsyncClient) -> None:
    token = await _register_and_login(client)
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/review",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_review_document_not_ready(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
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
        f"/api/v1/documents/{doc_id}/review",
        json={},
        headers=headers,
    )
    assert resp.status_code == 409


# ── List reviews ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_reviews_empty(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.get(f"/api/v1/documents/{doc.id}/reviews", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_reviews_after_creation(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    # Create two reviews
    with patch.object(ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA):
        await client.post(f"/api/v1/documents/{doc.id}/review", json={}, headers=headers)
        await client.post(f"/api/v1/documents/{doc.id}/review", json={}, headers=headers)

    resp = await client.get(f"/api/v1/documents/{doc.id}/reviews", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ── Get single review ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_review_success(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    with patch.object(ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA):
        create_resp = await client.post(
            f"/api/v1/documents/{doc.id}/review", json={}, headers=headers
        )

    review_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/documents/{doc.id}/reviews/{review_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == review_id
    assert data["overall_score"] == 8.0


@pytest.mark.asyncio
async def test_get_review_not_found(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/reviews/{uuid.uuid4()}",
        headers=headers,
    )
    assert resp.status_code == 404


# ── Issue classification ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_all_issue_types_accepted(client: AsyncClient, db: AsyncSession) -> None:
    """All issue types from the spec should be stored and returned correctly."""
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    all_types_review = {
        "overall_score": 5.0,
        "summary": "Many issues found.",
        "issues": [
            {"type": t, "severity": "low", "location": "p1", "description": "issue", "suggestion": "fix"}
            for t in ["grammar", "spelling", "style", "formatting", "clarity", "tone"]
        ],
    }
    mock_resp = {
        "message": {"content": json.dumps(all_types_review)},
        "done": True,
        "eval_count": 50,
    }

    with patch.object(ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=mock_resp):
        resp = await client.post(f"/api/v1/documents/{doc.id}/review", json={}, headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["issue_count"] == 6
    returned_types = {i["type"] for i in data["issues"]}
    assert returned_types == {"grammar", "spelling", "style", "formatting", "clarity", "tone"}


@pytest.mark.asyncio
async def test_review_score_stored_correctly(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.models.user import User
    res = await db.execute(select(User).where(User.email == "review_admin@example.com"))
    admin = res.scalar_one()
    doc = await _make_ready_doc(db, admin.id)

    perfect_review = {"overall_score": 10.0, "summary": "Perfect doc.", "issues": []}
    mock_resp = {"message": {"content": json.dumps(perfect_review)}, "done": True, "eval_count": 10}

    with patch.object(ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=mock_resp):
        resp = await client.post(f"/api/v1/documents/{doc.id}/review", json={}, headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["overall_score"] == 10.0
    assert data["issue_count"] == 0
