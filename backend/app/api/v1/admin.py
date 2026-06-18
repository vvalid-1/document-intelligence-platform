from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import generate_sse_token, hash_password, sha256, token_expiry
from app.models.user import SSEToken, User, UserInvitation
from app.schemas.admin import (
    AdminCreateUserRequest,
    AdminInviteRequest,
    AdminInviteResponse,
    AdminResetPasswordRequest,
    AdminUpdateRoleRequest,
    AdminUserListResponse,
    AdminUserResponse,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[User, Depends(require_admin)]


# ── List users ────────────────────────────────────────────────────────────────

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
) -> AdminUserListResponse:
    if page_size > 100:
        page_size = 100
    count = await db.scalar(select(func.count()).select_from(User))
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(u) for u in users],
        total=count or 0,
    )


# ── Create user directly ──────────────────────────────────────────────────────

@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=AdminUserResponse)
async def create_user(
    body: AdminCreateUserRequest,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.flush()
    await log_action(db, action="admin.user.create", user_id=admin.id, resource_type="user", resource_id=user.id, request=request)
    return AdminUserResponse.model_validate(user)


# ── Invite user ───────────────────────────────────────────────────────────────

@router.post("/users/invite", response_model=AdminInviteResponse)
async def invite_user(
    body: AdminInviteRequest,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminInviteResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    raw_token, token_hash = generate_sse_token()  # reuse same crypto quality
    expires_at = token_expiry(days=7)

    invitation = UserInvitation(
        email=body.email,
        role=body.role,
        invited_by=admin.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    await log_action(db, action="admin.user.invite", user_id=admin.id, resource_type="user_invitation", resource_id=invitation.id, request=request)

    return AdminInviteResponse(invitation_token=raw_token, email=body.email, role=body.role, expires_at=expires_at)


# ── Get user ──────────────────────────────────────────────────────────────────

async def _get_user(user_id: uuid.UUID, db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    return AdminUserResponse.model_validate(await _get_user(user_id, db))


# ── Update role ───────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_role(
    user_id: uuid.UUID,
    body: AdminUpdateRoleRequest,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    user = await _get_user(user_id, db)
    old_role = user.role
    user.role = body.role
    await log_action(db, action="admin.user.role_update", user_id=admin.id, resource_type="user", resource_id=user.id,
                     details={"old_role": old_role, "new_role": body.role}, request=request)
    return AdminUserResponse.model_validate(user)


# ── Activate / deactivate ─────────────────────────────────────────────────────

@router.patch("/users/{user_id}/activate", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def activate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    user = await _get_user(user_id, db)
    user.is_active = True
    await log_action(db, action="admin.user.activate", user_id=admin.id, resource_type="user", resource_id=user.id, request=request)
    return Response(status_code=204)


@router.patch("/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    user = await _get_user(user_id, db)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user.is_active = False
    await log_action(db, action="admin.user.deactivate", user_id=admin.id, resource_type="user", resource_id=user.id, request=request)
    return Response(status_code=204)


# ── Reset password ────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def reset_password(
    user_id: uuid.UUID,
    body: AdminResetPasswordRequest,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    user = await _get_user(user_id, db)
    user.hashed_password = hash_password(body.new_password)
    await log_action(db, action="admin.user.password_reset", user_id=admin.id, resource_type="user", resource_id=user.id, request=request)
    return Response(status_code=204)


# ── Hard delete (admin only) ──────────────────────────────────────────────────

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def hard_delete_user(
    user_id: uuid.UUID,
    request: Request,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    user = await _get_user(user_id, db)
    await log_action(db, action="admin.user.hard_delete", user_id=admin.id, resource_type="user", resource_id=user.id, request=request)
    await db.delete(user)
    return Response(status_code=204)
