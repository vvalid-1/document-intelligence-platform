from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.agent import AgentMessage, AgentSession, AgentTask
from app.models.document import Document
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    MessageResponse,
    SessionDetailResponse,
    SessionResponse,
    SourceCitation,
)
from app.agents.rag_agent import RAGAgent
from app.agents.base import TaskPayload
from app.models.user import User
from app.services.audit_service import log_action

router = APIRouter(prefix="/chat", tags=["chat"])


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionResponse)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionResponse:
    session = AgentSession(
        user_id=current_user.id,
        session_name=body.name,
        is_active=True,
    )
    db.add(session)
    await db.flush()

    await log_action(
        db,
        action="chat.session.create",
        user_id=current_user.id,
        resource_type="agent_session",
        resource_id=session.id,
        request=request,
    )

    return SessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SessionResponse]:
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.user_id == current_user.id)
        .order_by(AgentSession.created_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionDetailResponse:
    session = await _get_session_or_404(session_id, current_user.id, db)

    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num)
    )
    messages = result.scalars().all()

    return SessionDetailResponse(
        **SessionResponse.model_validate(session).model_dump(),
        messages=[MessageResponse.model_validate(m) for m in messages],
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def close_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    session = await _get_session_or_404(session_id, current_user.id, db)
    session.is_active = False
    await db.flush()
    return Response(status_code=204)


# ── Messages / Q&A ────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def ask_question(
    session_id: uuid.UUID,
    body: ChatRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
    session = await _get_session_or_404(session_id, current_user.id, db)

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Session is closed"
        )

    # Validate document_ids if provided
    doc_ids_str: list[str] | None = None
    if body.document_ids:
        for doc_id in body.document_ids:
            res = await db.execute(
                select(Document.id).where(
                    Document.id == doc_id,
                    Document.is_deleted.is_(False),
                    Document.status == "ready",
                )
            )
            if res.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document {doc_id} not found or not ready",
                )
        doc_ids_str = [str(d) for d in body.document_ids]

    # Compute next sequence_num
    seq_res = await db.execute(
        select(func.max(AgentMessage.sequence_num)).where(
            AgentMessage.session_id == session_id
        )
    )
    next_seq = (seq_res.scalar_one_or_none() or 0) + 1

    # Persist user message
    user_msg = AgentMessage(
        session_id=session_id,
        role="user",
        content=body.question,
        sequence_num=next_seq,
    )
    db.add(user_msg)
    await db.flush()

    # Run RAG agent
    agent = RAGAgent()
    payload = TaskPayload(
        task_type="qa_retrieval",
        session_id=session_id,
        user_id=current_user.id,
        document_id=None,
        input_data={
            "question": body.question,
            "document_ids": doc_ids_str,
            "top_k": body.top_k,
        },
    )
    result = await agent.run(payload, db)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Agent failed",
        )

    answer: str = result.output_data.get("answer", "")
    raw_sources: list[dict] = result.output_data.get("sources", [])
    task_id_str: str = result.output_data.get("task_id", "")
    task_id = uuid.UUID(task_id_str)

    # Persist assistant message
    asst_msg = AgentMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        agent_name=RAGAgent.AGENT_NAME,
        task_id=task_id,
        sequence_num=next_seq + 1,
    )
    db.add(asst_msg)
    await db.flush()

    await log_action(
        db,
        action="chat.message.ask",
        user_id=current_user.id,
        resource_type="agent_session",
        resource_id=session_id,
        details={"task_id": task_id_str, "sources_count": len(raw_sources)},
        request=request,
    )

    sources = [SourceCitation(**s) for s in raw_sources]

    return ChatResponse(
        message_id=asst_msg.id,
        session_id=session_id,
        answer=answer,
        sources=sources,
        task_id=task_id,
        token_count=result.token_count,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_session_or_404(
    session_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> AgentSession:
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session
