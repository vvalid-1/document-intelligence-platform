from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.translation_agent import TranslationAgent
from app.core.database import get_db
from app.core.deps import get_current_user, require_editor_or_admin
from app.models.agent import AgentSession
from app.models.document import Document, DocumentVersion
from app.models.user import User
from app.schemas.translation import TranslationRequest, TranslationResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/documents", tags=["translations"])


@router.post(
    "/{document_id}/translate",
    status_code=status.HTTP_201_CREATED,
    response_model=TranslationResponse,
)
async def translate_document(
    document_id: uuid.UUID,
    body: TranslationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> TranslationResponse:
    doc = await _get_ready_doc_or_error(document_id, current_user, db)

    session = AgentSession(
        user_id=current_user.id,
        session_name=f"translate:{document_id}",
        is_active=False,
    )
    db.add(session)
    await db.flush()

    agent = TranslationAgent()
    payload = TaskPayload(
        task_type="translate_document",
        session_id=session.id,
        user_id=current_user.id,
        document_id=document_id,
        input_data={
            "translator_id": str(current_user.id),
            "target_language": body.target_language,
        },
    )
    result = await agent.run(payload, db)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Translation failed",
        )

    version_id = uuid.UUID(result.output_data["version_id"])
    res = await db.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id)
    )
    version = res.scalar_one()

    await log_action(
        db,
        action="document.translate",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        details={
            "version_id": str(version_id),
            "version_number": result.output_data["version_number"],
            "target_language": body.target_language,
            "language_name": result.output_data["language_name"],
        },
        request=request,
    )

    return TranslationResponse.from_orm(
        version,
        target_language=result.output_data["target_language"],
        language_name=result.output_data["language_name"],
        text_preview=result.output_data["text_preview"],
        txt_path=result.output_data["txt_path"],
        pdf_path=result.output_data["pdf_path"],
    )


async def _get_ready_doc_or_error(
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
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for translation (status={doc.status})",
        )
    return doc
