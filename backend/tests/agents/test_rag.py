from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import chromadb
import pytest

from app.agents.base import AgentResult, TaskPayload, _CTX_LIMIT
from app.agents.rag_agent import RAGAgent

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chunks(n: int = 3) -> list[dict]:
    return [
        {
            "text": f"This is chunk number {i} with relevant information about topic {i}.",
            "document_id": str(uuid.uuid4()),
            "document_title": f"Document {i}",
            "page_number": i,
            "chunk_index": i,
            "similarity": round(0.95 - i * 0.05, 2),
        }
        for i in range(n)
    ]


def _make_agent() -> RAGAgent:
    return RAGAgent()


# ── Context building ──────────────────────────────────────────────────────────

def test_build_context_formats_sources() -> None:
    agent = _make_agent()
    chunks = _make_chunks(2)
    context, sources = agent._build_context(chunks)

    assert "[Source 1]" in context
    assert "[Source 2]" in context
    assert "Document 0" in context
    assert "Document 1" in context
    assert len(sources) == 2
    assert sources[0]["source_num"] == 1
    assert sources[1]["source_num"] == 2


def test_build_context_includes_page_numbers() -> None:
    agent = _make_agent()
    chunks = [
        {
            "text": "Some content",
            "document_id": str(uuid.uuid4()),
            "document_title": "My Doc",
            "page_number": 5,
            "chunk_index": 0,
            "similarity": 0.9,
        }
    ]
    context, _ = agent._build_context(chunks)
    assert "Page 5" in context


def test_build_context_excerpt_truncated() -> None:
    agent = _make_agent()
    long_text = "word " * 200  # 1000 chars
    chunks = [
        {
            "text": long_text,
            "document_id": str(uuid.uuid4()),
            "document_title": "Long Doc",
            "page_number": 1,
            "chunk_index": 0,
            "similarity": 0.8,
        }
    ]
    _, sources = agent._build_context(chunks)
    assert sources[0]["excerpt"].endswith("...")
    assert len(sources[0]["excerpt"]) <= 310  # 300 + "..."


def test_build_context_empty_chunks() -> None:
    agent = _make_agent()
    context, sources = agent._build_context([])
    assert context == ""
    assert sources == []


# ── Token counting and truncation ─────────────────────────────────────────────

def test_count_tokens_approximation() -> None:
    agent = _make_agent()
    text = "a" * 400  # 400 chars → ~100 tokens
    assert agent._count_tokens(text) == 100


def test_truncate_to_budget_under_limit() -> None:
    agent = _make_agent()
    text = "hello world"
    result = agent._truncate_to_budget(text, budget_tokens=1000)
    assert result == text


def test_truncate_to_budget_over_limit() -> None:
    agent = _make_agent()
    text = "word " * 500  # 2500 chars → ~625 tokens
    result = agent._truncate_to_budget(text, budget_tokens=100)
    assert len(result) <= 400 + 5  # small buffer for word boundary


# ── Think tag stripping ───────────────────────────────────────────────────────

def test_strip_think_tags() -> None:
    agent = _make_agent()
    raw = "<think>Let me reason about this...</think>The actual answer is 42."
    assert agent._strip_think_tags(raw) == "The actual answer is 42."


def test_strip_think_tags_multiline() -> None:
    agent = _make_agent()
    raw = "<think>\nMulti\nline\nreasoning\n</think>\nFinal answer."
    assert agent._strip_think_tags(raw) == "Final answer."


def test_strip_think_tags_none_present() -> None:
    agent = _make_agent()
    raw = "Clean response with no tags."
    assert agent._strip_think_tags(raw) == raw


# ── _retrieve_chunks ──────────────────────────────────────────────────────────

async def test_retrieve_chunks_empty_collection_returns_empty() -> None:
    agent = _make_agent()
    chroma_client = chromadb.EphemeralClient()
    col = chroma_client.get_or_create_collection(
        "document_chunks",
        embedding_function=None,
    )

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    with (
        patch("app.agents.rag_agent.embed_texts", side_effect=_fake_embed),
        patch("app.agents.rag_agent.get_document_collection", return_value=col),
    ):
        result = await agent._retrieve_chunks("test query", None, 5)
    assert result == []


async def test_retrieve_chunks_returns_results() -> None:
    agent = _make_agent()
    chroma_client = chromadb.EphemeralClient()
    col = chroma_client.get_or_create_collection(
        "document_chunks",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )

    doc_id = str(uuid.uuid4())
    col.add(
        ids=[f"{doc_id}_0", f"{doc_id}_1"],
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        documents=["First relevant chunk", "Second relevant chunk"],
        metadatas=[
            {"document_id": doc_id, "document_title": "Test", "page_number": 1, "chunk_index": 0, "owner_id": "", "created_at": "", "mime_type": "text/plain"},
            {"document_id": doc_id, "document_title": "Test", "page_number": 2, "chunk_index": 1, "owner_id": "", "created_at": "", "mime_type": "text/plain"},
        ],
    )

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    with (
        patch("app.agents.rag_agent.embed_texts", side_effect=_fake_embed),
        patch("app.agents.rag_agent.get_document_collection", return_value=col),
    ):
        result = await agent._retrieve_chunks("test query", None, 2)

    assert len(result) == 2
    assert all("text" in r for r in result)
    assert all("similarity" in r for r in result)
    assert all("document_title" in r for r in result)


async def test_retrieve_chunks_embed_failure_returns_empty() -> None:
    agent = _make_agent()

    async def _fail_embed(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Ollama unavailable")

    with patch("app.agents.rag_agent.embed_texts", side_effect=_fail_embed):
        result = await agent._retrieve_chunks("query", None, 5)
    assert result == []


# ── RAGAgent Q&A integration (mocked Ollama + ChromaDB) ──────────────────────

async def test_rag_agent_qa_returns_answer_and_sources(db) -> None:
    agent = _make_agent()
    session = await _make_session(db)

    chunks = _make_chunks(2)
    with (
        patch.object(RAGAgent, "_retrieve_chunks", new_callable=AsyncMock, return_value=chunks),
        patch.object(
            RAGAgent,
            "_call_ollama",
            new_callable=AsyncMock,
            return_value={
                "message": {"role": "assistant", "content": "Answer here [Source 1]."},
                "done": True,
                "eval_count": 30,
            },
        ),
    ):
        payload = TaskPayload(
            task_type="qa_retrieval",
            session_id=session.id,
            user_id=session.user_id,
            document_id=None,
            input_data={"question": "What is this about?", "top_k": 5},
        )
        result = await agent.run(payload, db)

    assert result.success is True
    assert "answer" in result.output_data
    assert "sources" in result.output_data
    assert len(result.output_data["sources"]) == 2
    assert result.token_count == 30
    assert "task_id" in result.output_data


async def test_rag_agent_qa_no_chunks(db) -> None:
    agent = _make_agent()
    session = await _make_session(db)

    with patch.object(RAGAgent, "_retrieve_chunks", new_callable=AsyncMock, return_value=[]):
        payload = TaskPayload(
            task_type="qa_retrieval",
            session_id=session.id,
            user_id=session.user_id,
            document_id=None,
            input_data={"question": "Anything?", "top_k": 5},
        )
        result = await agent.run(payload, db)

    assert result.success is True
    assert "could not find" in result.output_data["answer"].lower()
    assert result.output_data["sources"] == []


async def test_rag_agent_strips_think_tags(db) -> None:
    agent = _make_agent()
    session = await _make_session(db)

    with (
        patch.object(RAGAgent, "_retrieve_chunks", new_callable=AsyncMock, return_value=_make_chunks(1)),
        patch.object(
            RAGAgent,
            "_call_ollama",
            new_callable=AsyncMock,
            return_value={
                "message": {"role": "assistant", "content": "<think>Reasoning...</think>Clean answer."},
                "done": True,
                "eval_count": 5,
            },
        ),
    ):
        payload = TaskPayload(
            task_type="qa_retrieval",
            session_id=session.id,
            user_id=session.user_id,
            document_id=None,
            input_data={"question": "?", "top_k": 3},
        )
        result = await agent.run(payload, db)

    assert result.output_data["answer"] == "Clean answer."


async def test_rag_agent_task_persisted_in_db(db) -> None:
    from sqlalchemy import select
    from app.models.agent import AgentTask

    agent = _make_agent()
    session = await _make_session(db)

    with (
        patch.object(RAGAgent, "_retrieve_chunks", new_callable=AsyncMock, return_value=[]),
    ):
        payload = TaskPayload(
            task_type="qa_retrieval",
            session_id=session.id,
            user_id=session.user_id,
            document_id=None,
            input_data={"question": "Test", "top_k": 5},
        )
        result = await agent.run(payload, db)

    task_id = uuid.UUID(result.output_data["task_id"])
    res = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = res.scalar_one_or_none()
    assert task is not None
    assert task.status == "completed"
    assert task.agent_name == "search_rag"
    assert task.duration_ms is not None


async def test_rag_agent_timeout_handled(db) -> None:
    from app.core.config import settings

    agent = _make_agent()
    session = await _make_session(db)

    async def _slow_retrieve(*args, **kwargs):
        await asyncio.sleep(settings.AGENT_TIMEOUT_SECONDS + 1)
        return []

    with patch.object(RAGAgent, "_retrieve_chunks", side_effect=_slow_retrieve):
        original_timeout = settings.AGENT_TIMEOUT_SECONDS
        settings.AGENT_TIMEOUT_SECONDS = 0.05  # 50ms for test
        try:
            payload = TaskPayload(
                task_type="qa_retrieval",
                session_id=session.id,
                user_id=session.user_id,
                document_id=None,
                input_data={"question": "slow", "top_k": 5},
            )
            result = await agent.run(payload, db)
        finally:
            settings.AGENT_TIMEOUT_SECONDS = original_timeout

    assert result.timed_out is True
    assert result.success is False


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_session(db) -> "AgentSession":
    """Create a real User then AgentSession with both IDs flushed to DB."""
    from app.models.agent import AgentSession
    from app.models.user import User
    from app.core.security import hash_password

    user_id = uuid.uuid4()
    db.add(User(
        id=user_id,
        email=f"agent_test_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Agent Test",
        hashed_password=hash_password("testpassword1"),
        role="editor",
        is_active=True,
    ))
    await db.flush()  # must flush user first (FK: agent_sessions.user_id → users.id)

    session = AgentSession(user_id=user_id, is_active=True)
    db.add(session)
    await db.flush()  # flush session so session.id is assigned before test uses it
    return session
