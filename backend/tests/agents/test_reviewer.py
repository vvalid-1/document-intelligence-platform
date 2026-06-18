from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.reviewer_agent import ReviewerAgent
from app.models.document import DocumentReview

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ── Mock LLM response ─────────────────────────────────────────────────────────

_REVIEW_JSON = {
    "overall_score": 7.5,
    "summary": "The document is generally well-written with some grammatical and spelling issues.",
    "issues": [
        {
            "type": "grammar",
            "severity": "medium",
            "location": "First paragraph",
            "description": "Subject-verb agreement error.",
            "suggestion": "Change 'they was' to 'they were'.",
        },
        {
            "type": "spelling",
            "severity": "low",
            "location": "Second paragraph",
            "description": "Typo: 'recieve'.",
            "suggestion": "Change to 'receive'.",
        },
    ],
}

_MOCK_OLLAMA_RESPONSE = {
    "message": {"role": "assistant", "content": json.dumps(_REVIEW_JSON)},
    "done": True,
    "eval_count": 80,
}


def _make_agent() -> ReviewerAgent:
    return ReviewerAgent()


# ── JSON extraction tests ─────────────────────────────────────────────────────

def test_extract_review_json_direct() -> None:
    agent = _make_agent()
    result = agent._extract_review_json(json.dumps(_REVIEW_JSON))
    assert result["overall_score"] == 7.5
    assert len(result["issues"]) == 2


def test_extract_review_json_with_code_block() -> None:
    agent = _make_agent()
    wrapped = f"```json\n{json.dumps(_REVIEW_JSON)}\n```"
    result = agent._extract_review_json(wrapped)
    assert result["overall_score"] == 7.5


def test_extract_review_json_with_think_tags() -> None:
    agent = _make_agent()
    raw = f"<think>Let me analyze...</think>\n{json.dumps(_REVIEW_JSON)}"
    result = agent._extract_review_json(raw)
    assert result["overall_score"] == 7.5


def test_extract_review_json_embedded_in_text() -> None:
    agent = _make_agent()
    raw = f"Here is my review:\n{json.dumps(_REVIEW_JSON)}\nEnd of review."
    result = agent._extract_review_json(raw)
    assert result["overall_score"] == 7.5


def test_extract_review_json_fallback_on_garbage() -> None:
    agent = _make_agent()
    result = agent._extract_review_json("This is not JSON at all.")
    assert result["issues"] == []
    assert result["overall_score"] is None
    assert "summary" in result


# ── Issue sanitization tests ──────────────────────────────────────────────────

def test_sanitize_issues_valid() -> None:
    agent = _make_agent()
    raw = [
        {"type": "grammar", "severity": "high", "location": "p1", "description": "err", "suggestion": "fix"},
    ]
    result = agent._sanitize_issues(raw)
    assert len(result) == 1
    assert result[0]["type"] == "grammar"
    assert result[0]["severity"] == "high"


def test_sanitize_issues_invalid_type_defaults_to_style() -> None:
    agent = _make_agent()
    raw = [{"type": "unknown_type", "severity": "low", "location": "", "description": "", "suggestion": ""}]
    result = agent._sanitize_issues(raw)
    assert result[0]["type"] == "style"


def test_sanitize_issues_invalid_severity_defaults_to_low() -> None:
    agent = _make_agent()
    raw = [{"type": "grammar", "severity": "critical", "location": "", "description": "", "suggestion": ""}]
    result = agent._sanitize_issues(raw)
    assert result[0]["severity"] == "low"


def test_sanitize_issues_non_list_returns_empty() -> None:
    agent = _make_agent()
    assert agent._sanitize_issues("not a list") == []  # type: ignore[arg-type]


def test_sanitize_issues_skips_non_dict_items() -> None:
    agent = _make_agent()
    raw = ["a string", {"type": "style", "severity": "low", "location": "", "description": "", "suggestion": ""}]
    result = agent._sanitize_issues(raw)
    assert len(result) == 1


def test_sanitize_issues_truncates_long_fields() -> None:
    agent = _make_agent()
    raw = [{"type": "grammar", "severity": "low", "location": "x" * 300, "description": "y" * 600, "suggestion": "z" * 600}]
    result = agent._sanitize_issues(raw)
    assert len(result[0]["location"]) <= 200
    assert len(result[0]["description"]) <= 500
    assert len(result[0]["suggestion"]) <= 500


# ── Score validation tests ────────────────────────────────────────────────────

def test_validate_score_valid() -> None:
    agent = _make_agent()
    assert agent._validate_score(8.5, []) == 8.5


def test_validate_score_rounds_to_one_decimal() -> None:
    agent = _make_agent()
    assert agent._validate_score(7.543, []) == 7.5


def test_validate_score_clamps_invalid_to_fallback() -> None:
    agent = _make_agent()
    issues = [
        {"severity": "high"},
        {"severity": "medium"},
        {"severity": "low"},
    ]
    # fallback: 10 - 1.5 - 0.75 - 0.25 = 7.5
    score = agent._validate_score("not a number", issues)
    assert score == 7.5


def test_validate_score_out_of_range_uses_fallback() -> None:
    agent = _make_agent()
    score = agent._validate_score(15.0, [])
    assert score == 10.0  # no issues → 10.0


def test_validate_score_many_issues_floor_at_zero() -> None:
    agent = _make_agent()
    many_high = [{"severity": "high"}] * 10
    score = agent._validate_score(None, many_high)
    assert score == 0.0


# ── ReviewerAgent.run() integration ──────────────────────────────────────────

async def test_reviewer_agent_creates_review_record(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = _make_agent()
    with patch.object(
        ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA_RESPONSE
    ):
        payload = TaskPayload(
            task_type="review_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={"reviewer_id": str(session.user_id)},
        )
        result = await agent.run(payload, db)

    assert result.success is True
    assert "review_id" in result.output_data
    assert "task_id" in result.output_data

    review_id = uuid.UUID(result.output_data["review_id"])
    res = await db.execute(select(DocumentReview).where(DocumentReview.id == review_id))
    review = res.scalar_one_or_none()
    assert review is not None
    assert review.overall_score == 7.5
    assert len(review.issues) == 2
    assert review.task_id is not None


async def test_reviewer_agent_handles_no_chunks(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id = await _make_empty_document(db, session.user_id)

    agent = _make_agent()
    payload = TaskPayload(
        task_type="review_document",
        session_id=session.id,
        user_id=session.user_id,
        document_id=doc_id,
        input_data={"reviewer_id": str(session.user_id)},
    )
    result = await agent.run(payload, db)

    assert result.success is True
    review_id = uuid.UUID(result.output_data["review_id"])
    res = await db.execute(select(DocumentReview).where(DocumentReview.id == review_id))
    review = res.scalar_one()
    assert review.issues == []
    assert review.overall_score == 10.0


async def test_reviewer_agent_strips_think_tags_in_json(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    raw_with_think = f"<think>Reasoning here...</think>\n{json.dumps(_REVIEW_JSON)}"
    agent = _make_agent()
    with patch.object(
        ReviewerAgent,
        "_call_ollama",
        new_callable=AsyncMock,
        return_value={"message": {"content": raw_with_think}, "done": True, "eval_count": 40},
    ):
        payload = TaskPayload(
            task_type="review_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={"reviewer_id": str(session.user_id)},
        )
        result = await agent.run(payload, db)

    assert result.success is True
    review_id = uuid.UUID(result.output_data["review_id"])
    res = await db.execute(select(DocumentReview).where(DocumentReview.id == review_id))
    review = res.scalar_one()
    assert review.overall_score == 7.5


async def test_reviewer_agent_fallback_on_bad_json(db: AsyncSession) -> None:
    """When LLM returns non-JSON, agent should still succeed with fallback values."""
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = _make_agent()
    with patch.object(
        ReviewerAgent,
        "_call_ollama",
        new_callable=AsyncMock,
        return_value={"message": {"content": "I cannot provide a review in JSON format."}, "done": True},
    ):
        payload = TaskPayload(
            task_type="review_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={"reviewer_id": str(session.user_id)},
        )
        result = await agent.run(payload, db)

    assert result.success is True
    review_id = uuid.UUID(result.output_data["review_id"])
    res = await db.execute(select(DocumentReview).where(DocumentReview.id == review_id))
    review = res.scalar_one()
    assert review.issues == []
    assert review.overall_score == 10.0  # no issues → 10


async def test_reviewer_agent_task_status_completed(db: AsyncSession) -> None:
    from app.models.agent import AgentTask

    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = _make_agent()
    with patch.object(
        ReviewerAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA_RESPONSE
    ):
        payload = TaskPayload(
            task_type="review_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={"reviewer_id": str(session.user_id)},
        )
        result = await agent.run(payload, db)

    task_id = uuid.UUID(result.output_data["task_id"])
    res = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = res.scalar_one()
    assert task.status == "completed"
    assert task.agent_name == "reviewer"
    assert task.duration_ms is not None


async def test_reviewer_agent_focus_areas_passed_through(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = _make_agent()
    captured_messages: list = []

    async def _capture_call(messages, tools=None):
        captured_messages.extend(messages)
        return _MOCK_OLLAMA_RESPONSE

    with patch.object(ReviewerAgent, "_call_ollama", side_effect=_capture_call):
        payload = TaskPayload(
            task_type="review_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "reviewer_id": str(session.user_id),
                "focus_areas": ["grammar", "spelling"],
            },
        )
        await agent.run(payload, db)

    system_content = captured_messages[0]["content"]
    assert "grammar" in system_content
    assert "spelling" in system_content


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _make_session(db: AsyncSession):
    from app.core.security import hash_password
    from app.models.agent import AgentSession
    from app.models.user import User

    user_id = uuid.uuid4()
    db.add(User(
        id=user_id,
        email=f"reviewer_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Reviewer Test",
        hashed_password=hash_password("testpassword1"),
        role="editor",
        is_active=True,
    ))
    await db.flush()

    session = AgentSession(user_id=user_id, is_active=False)
    db.add(session)
    await db.flush()
    return session


async def _make_ready_document(db: AsyncSession, owner_id: uuid.UUID):
    from app.models.document import Document, DocumentChunk

    doc_id = uuid.uuid4()
    db.add(Document(
        id=doc_id,
        owner_id=owner_id,
        title="Test Review Doc",
        original_name="test.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=200,
        mime_type="text/plain",
        status="ready",
        chunk_count=2,
    ))
    await db.flush()

    chunks = []
    for i in range(2):
        c = DocumentChunk(
            document_id=doc_id,
            chroma_chunk_id=f"{doc_id}_{i}",
            chunk_index=i,
            chunk_text=f"Chunk {i}: They was going to the office to recieve the documents. The team was pleased with they're progress.",
            token_count=20,
        )
        db.add(c)
        chunks.append(c)
    await db.flush()
    return doc_id, chunks


async def _make_empty_document(db: AsyncSession, owner_id: uuid.UUID) -> uuid.UUID:
    from app.models.document import Document

    doc_id = uuid.uuid4()
    db.add(Document(
        id=doc_id,
        owner_id=owner_id,
        title="Empty Doc",
        original_name="empty.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=0,
        mime_type="text/plain",
        status="ready",
        chunk_count=0,
    ))
    await db.flush()
    return doc_id
