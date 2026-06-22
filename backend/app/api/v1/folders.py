from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_editor_or_admin
from app.models.document import Document
from app.models.folder import Folder
from app.models.user import User
from app.schemas.folder import FolderCreateRequest, FolderListResponse, FolderRenameRequest, FolderResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/folders", tags=["folders"])


def _folder_visible(folder: Folder, user: User) -> bool:
    if user.role == "admin":
        return True
    return folder.owner_id == user.id


async def _get_folder_or_404(folder_id: uuid.UUID, user: User, db: AsyncSession) -> Folder:
    res = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = res.scalar_one_or_none()
    if folder is None or not _folder_visible(folder, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


async def _folder_to_response(folder: Folder, db: AsyncSession) -> FolderResponse:
    count_res = await db.execute(
        select(func.count(Document.id)).where(
            Document.folder_id == folder.id,
            Document.is_deleted.is_(False),
        )
    )
    doc_count = count_res.scalar_one()
    return FolderResponse(
        id=folder.id,
        owner_id=folder.owner_id,
        name=folder.name,
        doc_count=doc_count,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.get("", response_model=FolderListResponse)
async def list_folders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FolderListResponse:
    q = select(Folder).order_by(Folder.name)
    if current_user.role != "admin":
        q = q.where(Folder.owner_id == current_user.id)

    rows = (await db.execute(q)).scalars().all()
    items = []
    for folder in rows:
        items.append(await _folder_to_response(folder, db))

    return FolderListResponse(items=items, total=len(items))


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> FolderResponse:
    existing = await db.execute(
        select(Folder).where(Folder.owner_id == current_user.id, Folder.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A folder with this name already exists")

    folder = Folder(id=uuid.uuid4(), owner_id=current_user.id, name=body.name)
    db.add(folder)
    await log_action(
        db,
        action="folder.create",
        user_id=current_user.id,
        resource_type="folder",
        resource_id=folder.id,
        details={"name": body.name},
        request=request,
    )
    await db.flush()
    return await _folder_to_response(folder, db)


@router.patch("/{folder_id}", response_model=FolderResponse)
async def rename_folder(
    folder_id: uuid.UUID,
    body: FolderRenameRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> FolderResponse:
    folder = await _get_folder_or_404(folder_id, current_user, db)

    conflict = await db.execute(
        select(Folder).where(
            Folder.owner_id == folder.owner_id,
            Folder.name == body.name,
            Folder.id != folder_id,
        )
    )
    if conflict.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A folder with this name already exists")

    folder.name = body.name
    await log_action(
        db,
        action="folder.rename",
        user_id=current_user.id,
        resource_type="folder",
        resource_id=folder.id,
        details={"name": body.name},
        request=request,
    )
    await db.flush()
    await db.refresh(folder)
    return await _folder_to_response(folder, db)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_folder(
    folder_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_editor_or_admin)],
) -> Response:
    folder = await _get_folder_or_404(folder_id, current_user, db)
    await log_action(
        db,
        action="folder.delete",
        user_id=current_user.id,
        resource_type="folder",
        resource_id=folder.id,
        details={"name": folder.name},
        request=request,
    )
    await db.delete(folder)
    return Response(status_code=204)


@router.get("/{folder_id}/documents")
async def list_folder_documents(
    folder_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = 1,
    page_size: int = 20,
) -> dict:
    from app.schemas.document import DocumentListResponse, DocumentResponse

    await _get_folder_or_404(folder_id, current_user, db)

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    base_q = select(Document).where(
        Document.folder_id == folder_id,
        Document.is_deleted.is_(False),
    )
    if current_user.role == "viewer":
        base_q = base_q.where(Document.owner_id == current_user.id)

    total_res = await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )
    total = total_res.scalar_one()

    docs_res = await db.execute(
        base_q.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = docs_res.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    ).model_dump()
