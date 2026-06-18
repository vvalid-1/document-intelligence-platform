from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    type: str
    severity: str
    location: str
    description: str
    suggestion: str


class ReviewRequest(BaseModel):
    focus_areas: list[str] | None = Field(
        default=None,
        description="Optional: limit review to specific issue types (grammar, spelling, style, formatting, clarity, tone)",
    )


class ReviewResponse(BaseModel):
    id: UUID
    document_id: UUID
    task_id: UUID | None
    reviewer_id: UUID
    overall_score: float | None
    summary: str | None
    issues: list[ReviewIssue]
    issue_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, review: object) -> "ReviewResponse":
        from app.models.document import DocumentReview
        r: DocumentReview = review  # type: ignore[assignment]
        return cls(
            id=r.id,
            document_id=r.document_id,
            task_id=r.task_id,
            reviewer_id=r.reviewer_id,
            overall_score=r.overall_score,
            summary=r.summary,
            issues=[ReviewIssue(**i) for i in (r.issues or [])],
            issue_count=len(r.issues or []),
            created_at=r.created_at,
        )


class IssueSummary(BaseModel):
    type: str
    count: int
    high: int
    medium: int
    low: int


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
