from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

pytestmark = pytest.mark.asyncio(loop_scope="session")

_FAKE_DOC_ID_A = str(uuid.uuid4())
_FAKE_DOC_ID_B = str(uuid.uuid4())

_FAKE_EMBEDDING = [[0.1] * 10]

_CHROMA_TWO_DOCS = {
    "documents": [["Text about budget planning.", "Another budget reference.", "Scholarship information."]],
    "metadatas": [
        [
            {"document_id": _FAKE_DOC_ID_A, "document_title": "Budget Report", "chunk_index": 0, "page_number": 1},
            {"document_id": _FAKE_DOC_ID_A, "document_title": "Budget Report", "chunk_index": 1, "page_number": 2},
            {"document_id": _FAKE_DOC_ID_B, "document_title": "Education Plan", "chunk_index": 0, "page_number": 1},
        ]
    ],
    "distances": [[0.05, 0.12, 0.20]],
}

_CHROMA_EMPTY = {
    "documents": [[]],
    "metadatas": [[]],
    "distances": [[]],
}


async def _register_and_login(
    client: AsyncClient,
    email: str = "search_admin@example.com",
) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Search Admin", "password": "securepassword1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword1"},
    )
    return resp.json().get("access_token", "")


async def _make_ready_doc(db: AsyncSession, doc_id: str, title: str, owner_id: uuid.UUID) -> Document:
    doc = Document(
        id=uuid.UUID(doc_id),
        owner_id=owner_id,
        title=title,
        original_name=f"{title}.pdf",
        file_path=f"{doc_id}/original.pdf",
        file_size_bytes=1000,
        mime_type="application/pdf",
        status="ready",
        chunk_count=2,
    )
    db.add(doc)
    await db.flush()
    return doc


def _mock_collection(chroma_result: dict, count: int = 3) -> MagicMock:
    col = MagicMock()
    col.count.return_value = count
    col.query.return_value = chroma_result
    return col


# ── Auth guards ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/search", json={"query": "budget"})
    assert resp.status_code == 403


# ── Input validation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_empty_query_rejected(client: AsyncClient) -> None:
    token = await _register_and_login(client, "search_empty@example.com")
    resp = await client.post(
        "/api/v1/search",
        json={"query": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_top_k_too_large_rejected(client: AsyncClient) -> None:
    token = await _register_and_login(client, "search_topk@example.com")
    resp = await client.post(
        "/api/v1/search",
        json={"query": "budget", "top_k": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── Empty collection ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_empty_collection_returns_empty(client: AsyncClient) -> None:
    token = await _register_and_login(client, "search_empty_col@example.com")
    empty_col = MagicMock()
    empty_col.count.return_value = 0

    with (
        patch("app.api.v1.search.embed_texts", return_value=_FAKE_EMBEDDING),
        patch("app.api.v1.search.get_document_collection", return_value=empty_col),
    ):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "budget"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hits"] == 0
    assert body["total_documents"] == 0
    assert body["groups"] == []


# ── Successful search ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_groups_results_by_document(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "search_groups@example.com")

    from app.models.user import User
    from sqlalchemy import select
    res = await db.execute(select(User).where(User.email == "search_groups@example.com"))
    user = res.scalar_one()

    await _make_ready_doc(db, _FAKE_DOC_ID_A, "Budget Report", user.id)
    await _make_ready_doc(db, _FAKE_DOC_ID_B, "Education Plan", user.id)

    col = _mock_collection(_CHROMA_TWO_DOCS)

    with (
        patch("app.api.v1.search.embed_texts", return_value=_FAKE_EMBEDDING),
        patch("app.api.v1.search.get_document_collection", return_value=col),
    ):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "budget scholarship"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_documents"] == 2
    assert body["total_hits"] == 3

    titles = {g["document_title"] for g in body["groups"]}
    assert "Budget Report" in titles
    assert "Education Plan" in titles

    budget_group = next(g for g in body["groups"] if g["document_title"] == "Budget Report")
    assert budget_group["match_count"] == 2


@pytest.mark.asyncio
async def test_search_groups_sorted_by_best_similarity(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "search_sort@example.com")

    from app.models.user import User
    from sqlalchemy import select
    res = await db.execute(select(User).where(User.email == "search_sort@example.com"))
    user = res.scalar_one()

    doc_id_a = str(uuid.uuid4())
    doc_id_b = str(uuid.uuid4())
    await _make_ready_doc(db, doc_id_a, "High Relevance Doc", user.id)
    await _make_ready_doc(db, doc_id_b, "Low Relevance Doc", user.id)

    chroma_result = {
        "documents": [["Low relevance text.", "Very relevant text."]],
        "metadatas": [[
            {"document_id": doc_id_b, "document_title": "Low Relevance Doc", "chunk_index": 0, "page_number": 1},
            {"document_id": doc_id_a, "document_title": "High Relevance Doc", "chunk_index": 0, "page_number": 1},
        ]],
        "distances": [[0.40, 0.02]],
    }
    col = _mock_collection(chroma_result, count=2)

    with (
        patch("app.api.v1.search.embed_texts", return_value=_FAKE_EMBEDDING),
        patch("app.api.v1.search.get_document_collection", return_value=col),
    ):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "relevant"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    groups = resp.json()["groups"]
    assert groups[0]["document_title"] == "High Relevance Doc"
    assert groups[0]["best_similarity"] > groups[1]["best_similarity"]


@pytest.mark.asyncio
async def test_search_deleted_doc_excluded(client: AsyncClient, db: AsyncSession) -> None:
    token = await _register_and_login(client, "search_deleted@example.com")

    from app.models.user import User
    from sqlalchemy import select
    res = await db.execute(select(User).where(User.email == "search_deleted@example.com"))
    user = res.scalar_one()

    deleted_id = str(uuid.uuid4())
    deleted_doc = Document(
        id=uuid.UUID(deleted_id),
        owner_id=user.id,
        title="Deleted Document",
        original_name="deleted.pdf",
        file_path=f"{deleted_id}/original.pdf",
        file_size_bytes=500,
        mime_type="application/pdf",
        status="ready",
        chunk_count=1,
        is_deleted=True,
    )
    db.add(deleted_doc)
    await db.flush()

    chroma_result = {
        "documents": [["Content from a deleted document."]],
        "metadatas": [[
            {"document_id": deleted_id, "document_title": "Deleted Document", "chunk_index": 0, "page_number": 1},
        ]],
        "distances": [[0.05]],
    }
    col = _mock_collection(chroma_result, count=1)

    with (
        patch("app.api.v1.search.embed_texts", return_value=_FAKE_EMBEDDING),
        patch("app.api.v1.search.get_document_collection", return_value=col),
    ):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "deleted content"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hits"] == 0
    assert body["total_documents"] == 0


@pytest.mark.asyncio
async def test_search_embed_failure_returns_503(client: AsyncClient) -> None:
    token = await _register_and_login(client, "search_503@example.com")

    with patch("app.api.v1.search.embed_texts", side_effect=RuntimeError("Ollama down")):
        resp = await client.post(
            "/api/v1/search",
            json={"query": "budget"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 503
    assert "EMBED_UNAVAILABLE" in resp.json()["detail"]
