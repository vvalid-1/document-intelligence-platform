from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class TranslationRequest(BaseModel):
    target_language: Literal["en", "fr", "ar"]


class TranslationResponse(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    task_id: UUID | None
    target_language: str
    language_name: str
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
        target_language: str,
        language_name: str,
        text_preview: str,
        txt_path: str,
        pdf_path: str,
    ) -> "TranslationResponse":
        from app.models.document import DocumentVersion

        v: DocumentVersion = version  # type: ignore[assignment]
        return cls(
            id=v.id,
            document_id=v.document_id,
            version_number=v.version_number,
            task_id=v.task_id,
            target_language=target_language,
            language_name=language_name,
            change_summary=v.change_summary or "",
            text_preview=text_preview,
            txt_path=txt_path,
            pdf_path=pdf_path,
            created_at=v.created_at,
        )
