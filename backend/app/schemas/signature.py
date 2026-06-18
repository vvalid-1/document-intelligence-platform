from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SignatureRequest(BaseModel):
    signature_type: Literal["typed", "drawn"]
    typed_text: str | None = Field(default=None, max_length=200)
    image_base64: str | None = Field(default=None, description="Base64-encoded PNG for drawn signatures")
    x: float = Field(..., ge=0, description="X coordinate in PDF points from left edge")
    y: float = Field(..., ge=0, description="Y coordinate in PDF points from top edge")
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    field_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def check_signature_data(self) -> "SignatureRequest":
        if self.signature_type == "typed" and not (self.typed_text or "").strip():
            raise ValueError("typed_text is required and must be non-empty for typed signatures")
        if self.signature_type == "drawn" and not self.image_base64:
            raise ValueError("image_base64 is required for drawn signatures")
        return self


class SignatureResponse(BaseModel):
    id: UUID
    document_id: UUID
    signed_by: UUID
    version_id: UUID | None
    version_number: int | None
    signature_type: str
    field_name: str | None
    page_number: int | None
    position_data: dict | None
    signature_image_path: str | None
    signed_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(
        cls, sig: object, version_number: int | None = None
    ) -> "SignatureResponse":
        from app.models.document import Signature

        s: Signature = sig  # type: ignore[assignment]
        return cls(
            id=s.id,
            document_id=s.document_id,
            signed_by=s.signed_by,
            version_id=s.version_id,
            version_number=version_number,
            signature_type=s.signature_type,
            field_name=s.field_name,
            page_number=s.page_number,
            position_data=s.position_data,
            signature_image_path=s.signature_image_path,
            signed_at=s.signed_at,
        )


class SignatureListResponse(BaseModel):
    items: list[SignatureResponse]
    total: int
