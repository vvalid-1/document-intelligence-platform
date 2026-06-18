from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.editor_agent import EditorAgent
from app.models.document import DocumentVersion

pytestmark = pytest.mark.asyncio(loop_scope="session")

_EDITED_TEXT = "This is the corrected document text with proper grammar and spelling."

_MOCK_OLLAMA = {
    "message": {"role": "assistant", "content": _EDITED_TEXT},
    "done": True,
    "eval_count": 30,
}

_FAKE_TXT = "doc-id/v1_edited.txt"
_FAKE_PDF = "doc-id/v1_edited.pdf"


def _mock_save(*_args, **_kwargs):
    return _FAKE_TXT, _FAKE_PDF


# ── Unit tests for helpers ────────────────────────────────────────────────────

def test_editor_agent_strips_think_tags() -> None:
    agent = EditorAgent()
    raw = "<think>Let me rewrite this section...</think>\nHere is the edited text."
    result = agent._strip_think_tags(raw)
    assert "<think>" not in result
    assert "Here is the edited text." in result


def test_editor_agent_truncates_to_budget() -> None:
    agent = EditorAgent()
    long_text = "word " * 10000
    truncated = agent._truncate_to_budget(long_text, 100)
    assert len(truncated) <= 100 * 4 + 5  # budget_tokens * chars_per_token + slack


def test_editor_agent_count_tokens() -> None:
    agent = EditorAgent()
    # Approximately 1 token per 4 chars
    assert agent._count_tokens("hello world") == max(1, len("hello world") // 4)


# ── Integration tests for EditorAgent.run() ───────────────────────────────────

async def test_editor_agent_creates_version_record(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Fix grammar errors",
            },
        )
        result = await agent.run(payload, db)

    assert result.success is True
    assert "version_id" in result.output_data
    assert result.output_data["version_number"] == 1

    version_id = uuid.UUID(result.output_data["version_id"])
    res = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    version = res.scalar_one_or_none()
    assert version is not None
    assert version.version_number == 1
    assert version.agent_name == "editor"
    assert version.task_id is not None
    assert version.change_summary == "Fix grammar errors"


async def test_editor_agent_version_number_increments(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        for n in range(1, 4):
            payload = TaskPayload(
                task_type="edit_document",
                session_id=session.id,
                user_id=session.user_id,
                document_id=doc_id,
                input_data={
                    "editor_id": str(session.user_id),
                    "instruction": f"Edit {n}",
                },
            )
            result = await agent.run(payload, db)
            assert result.output_data["version_number"] == n


async def test_editor_agent_returns_text_preview(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Improve clarity",
            },
        )
        result = await agent.run(payload, db)

    assert result.output_data["text_preview"].startswith(_EDITED_TEXT[:20])


async def test_editor_agent_strips_think_tags_from_response(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    raw_with_think = f"<think>I'll restructure this...</think>\n{_EDITED_TEXT}"
    mock_resp = {"message": {"content": raw_with_think}, "done": True, "eval_count": 20}

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=mock_resp),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Restructure paragraphs",
            },
        )
        result = await agent.run(payload, db)

    assert "<think>" not in result.output_data["text_preview"]
    assert _EDITED_TEXT[:20] in result.output_data["text_preview"]


async def test_editor_agent_fails_on_empty_document(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id = await _make_empty_document(db, session.user_id)

    agent = EditorAgent()
    payload = TaskPayload(
        task_type="edit_document",
        session_id=session.id,
        user_id=session.user_id,
        document_id=doc_id,
        input_data={
            "editor_id": str(session.user_id),
            "instruction": "Fix grammar",
        },
    )
    result = await agent.run(payload, db)

    assert result.success is False
    assert "no text content" in (result.error or "").lower()


async def test_editor_agent_task_status_completed(db: AsyncSession) -> None:
    from app.models.agent import AgentTask

    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Improve writing style",
            },
        )
        result = await agent.run(payload, db)

    task_id = uuid.UUID(result.output_data["task_id"])
    res = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = res.scalar_one()
    assert task.status == "completed"
    assert task.agent_name == "editor"
    assert task.duration_ms is not None
    assert task.token_count == 30


async def test_editor_agent_passes_instruction_in_message(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    captured: list = []

    async def _capture(messages, tools=None):
        captured.extend(messages)
        return _MOCK_OLLAMA

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", side_effect=_capture),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Replace 'hello' with 'greetings'",
            },
        )
        await agent.run(payload, db)

    user_msg = next(m for m in captured if m["role"] == "user")
    assert "Replace 'hello' with 'greetings'" in user_msg["content"]


async def test_editor_agent_stores_paths_in_version_metadata(db: AsyncSession) -> None:
    session = await _make_session(db)
    doc_id, _ = await _make_ready_document(db, session.user_id)

    agent = EditorAgent()
    with (
        patch.object(EditorAgent, "_call_ollama", new_callable=AsyncMock, return_value=_MOCK_OLLAMA),
        patch("app.agents.editor_agent.save_version_files", side_effect=_mock_save),
    ):
        payload = TaskPayload(
            task_type="edit_document",
            session_id=session.id,
            user_id=session.user_id,
            document_id=doc_id,
            input_data={
                "editor_id": str(session.user_id),
                "instruction": "Remove last paragraph",
            },
        )
        result = await agent.run(payload, db)

    version_id = uuid.UUID(result.output_data["version_id"])
    res = await db.execute(select(DocumentVersion).where(DocumentVersion.id == version_id))
    version = res.scalar_one()
    assert version.version_metadata is not None
    assert "txt_path" in version.version_metadata
    assert "pdf_path" in version.version_metadata


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _make_session(db: AsyncSession):
    from app.core.security import hash_password
    from app.models.agent import AgentSession
    from app.models.user import User

    user_id = uuid.uuid4()
    db.add(User(
        id=user_id,
        email=f"editor_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Editor Test",
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
        title="Test Edit Doc",
        original_name="test.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=300,
        mime_type="text/plain",
        status="ready",
        chunk_count=2,
    ))
    await db.flush()

    for i in range(2):
        db.add(DocumentChunk(
            document_id=doc_id,
            chroma_chunk_id=f"{doc_id}_{i}",
            chunk_index=i,
            chunk_text=f"Chunk {i}: Hello world. This is a test document with some gramatical errors and mispelled words.",
            token_count=18,
        ))
    await db.flush()
    return doc_id, None


async def _make_empty_document(db: AsyncSession, owner_id: uuid.UUID) -> uuid.UUID:
    from app.models.document import Document

    doc_id = uuid.uuid4()
    db.add(Document(
        id=doc_id,
        owner_id=owner_id,
        title="Empty Edit Doc",
        original_name="empty.txt",
        file_path=f"{doc_id}/original.txt",
        file_size_bytes=0,
        mime_type="text/plain",
        status="ready",
        chunk_count=0,
    ))
    await db.flush()
    return doc_id
