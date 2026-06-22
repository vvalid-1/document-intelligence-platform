from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    original_name: str
    file_size_bytes: int
    mime_type: str
    page_count: int | None
    chunk_count: int | None
    status: str
    processing_step: str | None
    error_message: str | None
    is_archived: bool
    archived_at: datetime | None
    is_favorite: bool
    is_deleted: bool
    deleted_at: datetime | None
    owner_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BulkActionRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=50)


class BulkFavoriteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1, max_length=50)
    value: bool


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentPatchRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    created_by: UUID
    file_path: str
    change_summary: str | None
    agent_name: str | None
    task_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    status: str
    stream_url: str


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: str
    progress_percent: int
    progress_step: str | None
    chunk_count: int | None
    error_message: str | None
