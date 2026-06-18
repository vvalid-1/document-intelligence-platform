from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    name: str | None = Field(None, max_length=255)


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    agent_name: str | None
    sequence_num: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse]


class SourceCitation(BaseModel):
    source_num: int
    chunk_index: int
    document_id: str
    document_title: str
    page_number: int | None
    excerpt: str
    similarity_score: float


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    message_id: UUID
    session_id: UUID
    answer: str
    sources: list[SourceCitation]
    task_id: UUID
    token_count: int | None


class SummarizeRequest(BaseModel):
    length: str = Field(default="medium", pattern="^(short|medium|long)$")


class SummarizeResponse(BaseModel):
    document_id: UUID
    summary: str
    chunk_count: int
    token_count: int | None
    task_id: UUID
