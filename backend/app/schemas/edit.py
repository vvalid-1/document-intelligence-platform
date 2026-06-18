from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EditRequest(BaseModel):
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language edit instruction (e.g. 'Replace X with Y', 'Remove paragraph 2')",
    )


class EditResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    task_id: UUID | None
    change_summary: str
    text_preview: str
    txt_path: str
    pdf_path: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(
        cls,
        version: object,
        text_preview: str,
        txt_path: str,
        pdf_path: str,
    ) -> "EditResponse":
        from app.models.document import DocumentVersion

        v: DocumentVersion = version  # type: ignore[assignment]
        return cls(
            id=v.id,
            document_id=v.document_id,
            version_number=v.version_number,
            task_id=v.task_id,
            change_summary=v.change_summary or "",
            text_preview=text_preview,
            txt_path=txt_path,
            pdf_path=pdf_path,
            created_at=v.created_at,
        )


class EditListResponse(BaseModel):
    items: list[EditResponse]
    total: int
