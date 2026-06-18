from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import TaskPayload
from app.agents.signature_agent import SignatureAgent
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.agent import AgentSession
from app.models.document import Document, DocumentVersion, Signature
from app.models.user import User
from app.schemas.signature import SignatureListResponse, SignatureRequest, SignatureResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/documents", tags=["signatures"])


@router.post(
    "/{document_id}/sign",
    status_code=status.HTTP_201_CREATED,
    response_model=SignatureResponse,
)
async def sign_document(
    document_id: uuid.UUID,
    body: SignatureRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SignatureResponse:
    await _get_ready_doc_or_error(document_id, current_user, db)

    session = AgentSession(
        user_id=current_user.id,
        session_name=f"sign:{document_id}",
        is_active=False,
    )
    db.add(session)
    await db.flush()

    ip: str | None = None
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )

    agent = SignatureAgent()
    payload = TaskPayload(
        task_type="sign_document",
        session_id=session.id,
        user_id=current_user.id,
        document_id=document_id,
        input_data={
            "signer_id": str(current_user.id),
            "signature_type": body.signature_type,
            "typed_text": body.typed_text,
            "image_base64": body.image_base64,
            "x": body.x,
            "y": body.y,
            "page_number": body.page_number,
            "field_name": body.field_name,
            "ip_address": ip,
            "user_agent": request.headers.get("User-Agent"),
        },
    )
    result = await agent.run(payload, db)

    if not result.success:
        _code = status.HTTP_422_UNPROCESSABLE_ENTITY
        _err = result.error or "Signing failed"
        if "not found" in _err.lower() or "no signable" in _err.lower():
            _code = status.HTTP_404_NOT_FOUND
        elif "out of range" in _err.lower() or "outside" in _err.lower():
            _code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=_code, detail=_err)

    sig_id = uuid.UUID(result.output_data["signature_id"])
    version_number: int = result.output_data["version_number"]

    res = await db.execute(select(Signature).where(Signature.id == sig_id))
    sig = res.scalar_one()

    await log_action(
        db,
        action="document.sign",
        user_id=current_user.id,
        resource_type="document",
        resource_id=document_id,
        details={
            "signature_id": str(sig_id),
            "signature_type": body.signature_type,
            "page_number": body.page_number,
            "version_number": version_number,
        },
        request=request,
    )

    return SignatureResponse.from_orm_model(sig, version_number=version_number)


@router.get(
    "/{document_id}/signatures",
    response_model=SignatureListResponse,
)
async def list_signatures(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SignatureListResponse:
    await _get_doc_or_404(document_id, current_user, db)

    count_res = await db.execute(
        select(func.count()).where(Signature.document_id == document_id)
    )
    total: int = count_res.scalar_one()

    res = await db.execute(
        select(Signature)
        .where(Signature.document_id == document_id)
        .order_by(Signature.signed_at.desc())
    )
    sigs = res.scalars().all()

    # Resolve version numbers for each signature
    items = []
    for s in sigs:
        ver_num: int | None = None
        if s.version_id is not None:
            vr = await db.execute(
                select(DocumentVersion.version_number).where(DocumentVersion.id == s.version_id)
            )
            ver_num = vr.scalar_one_or_none()
        items.append(SignatureResponse.from_orm_model(s, version_number=ver_num))

    return SignatureListResponse(items=items, total=total)


@router.get(
    "/{document_id}/signatures/{signature_id}",
    response_model=SignatureResponse,
)
async def get_signature(
    document_id: uuid.UUID,
    signature_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SignatureResponse:
    await _get_doc_or_404(document_id, current_user, db)

    res = await db.execute(
        select(Signature).where(
            Signature.id == signature_id,
            Signature.document_id == document_id,
        )
    )
    sig = res.scalar_one_or_none()
    if sig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signature not found")

    ver_num: int | None = None
    if sig.version_id is not None:
        vr = await db.execute(
            select(DocumentVersion.version_number).where(DocumentVersion.id == sig.version_id)
        )
        ver_num = vr.scalar_one_or_none()

    return SignatureResponse.from_orm_model(sig, version_number=ver_num)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if user.role == "viewer" and doc.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return doc


async def _get_ready_doc_or_error(
    document_id: uuid.UUID, user: User, db: AsyncSession
) -> Document:
    doc = await _get_doc_or_404(document_id, user, db)
    if doc.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready for signing (status={doc.status})",
        )
    return doc
