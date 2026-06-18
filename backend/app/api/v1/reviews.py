from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.reviewer_agent import ReviewerAgent
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.agent import AgentSession
from app.models.document import Document, DocumentReview
from app.models.user import User
from app.schemas.review import ReviewListResponse, ReviewRequest, ReviewResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/documents", tags=["reviews"])


@router.post(
    "/{document_id}/review",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
)
async def create_review(
    document_id: uuid.UUID,
    body: ReviewRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewResponse:
    doc = await _get_ready_doc_or_error(document_id, current_user, db)

    session = AgentSession(
        user_id=current_user.id,
        session_name=f"review:{document_id}",
        is_active=False,
    )
    db.add(session)
    await db.flush()

    agent = ReviewerAgent()
    payload = TaskPayload(
        task_type="review_document",
        session_id=session.id,
        user_id=current_user.id,
        document_id=document_id,
        input_data={
            "reviewer_id": str(current_user.id),
            "focus_areas": body.focus_areas,
        },
    )
    result = await agent.run(payload, db)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Review failed",
        )

    review_id = uuid.UUID(result.output_data["review_id"])
    res = await db.execute(
        select(DocumentReview).where(DocumentReview.id == review_id)
    )
    review = res.scalar_one()

    await log_action(
        db,
        action="document.review.create",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        details={
            "review_id": str(review_id),
            "score": review.overall_score,
            "issue_count": len(review.issues or []),
        },
        request=request,
    )

    return ReviewResponse.from_orm_model(review)


@router.get(
    "/{document_id}/reviews",
    response_model=ReviewListResponse,
)
async def list_reviews(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewListResponse:
    await _get_doc_or_404(document_id, current_user, db)

    count_res = await db.execute(
        select(func.count()).where(DocumentReview.document_id == document_id)
    )
    total: int = count_res.scalar_one()

    res = await db.execute(
        select(DocumentReview)
        .where(DocumentReview.document_id == document_id)
        .order_by(DocumentReview.created_at.desc())
    )
    reviews = res.scalars().all()

    return ReviewListResponse(
        items=[ReviewResponse.from_orm_model(r) for r in reviews],
        total=total,
    )


@router.get(
    "/{document_id}/reviews/{review_id}",
    response_model=ReviewResponse,
)
async def get_review(
    document_id: uuid.UUID,
    review_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReviewResponse:
    await _get_doc_or_404(document_id, current_user, db)

    res = await db.execute(
        select(DocumentReview).where(
            DocumentReview.id == review_id,
            DocumentReview.document_id == document_id,
        )
    )
    review = res.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
        )
    return ReviewResponse.from_orm_model(review)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_doc_or_404(
    document_id: uuid.UUID, user: User, db: AsyncSession
) -> Document:
    res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.is_deleted.is_(False),
        )
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if user.role == "viewer" and doc.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    return doc


async def _get_ready_doc_or_error(
    document_id: uuid.UUID, user: User, db: AsyncSession
) -> Document:
    doc = await _get_doc_or_404(document_id, user, db)
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for review (status={doc.status})",
        )
    return doc
