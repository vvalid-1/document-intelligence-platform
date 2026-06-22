from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FolderRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FolderResponse(BaseModel):
    id: UUID
    owner_id: UUID | None
    name: str
    doc_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderListResponse(BaseModel):
    items: list[FolderResponse]
    total: int
