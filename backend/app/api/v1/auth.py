from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_sse_token,
    hash_password,
    sha256,
    token_expiry,
    verify_password,
)
from app.models.user import RefreshToken, SSEToken, User, UserInvitation
from app.schemas.auth import (
    ChangePasswordRequest,
    InviteAcceptRequest,
    LoginRequest,
    RegisterRequest,
    SSETokenResponse,
    TokenResponse,
    UserResponse,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=False,  # set True in production with HTTPS
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )


# ── Register (first user only) ────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    count_result = await db.execute(select(func.count()).select_from(User))
    user_count: int = count_result.scalar_one()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="REGISTRATION_CLOSED",
        )

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    role = "admin"  # first user is always admin
    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=role,
    )
    db.add(user)
    await db.flush()

    await log_action(db, action="user.register", user_id=user.id, resource_type="user", resource_id=user.id, request=request)

    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=token_expiry(days=7)))
    _set_refresh_cookie(response, raw_refresh)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


# ── Accept invitation ─────────────────────────────────────────────────────────

@router.post("/invite/accept", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def accept_invitation(
    body: InviteAcceptRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    token_hash = sha256(body.token)
    now = datetime.now(UTC)

    inv_result = await db.execute(
        select(UserInvitation).where(
            UserInvitation.token_hash == token_hash,
            UserInvitation.accepted_at.is_(None),
            UserInvitation.expires_at > now,
        )
    )
    invitation = inv_result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVITATION_INVALID_OR_EXPIRED")

    existing = await db.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=invitation.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=invitation.role,
    )
    db.add(user)
    invitation.accepted_at = now
    await db.flush()

    await log_action(db, action="user.register", user_id=user.id, resource_type="user", resource_id=user.id,
                     details={"via": "invitation"}, request=request)

    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=token_expiry(days=7)))
    _set_refresh_cookie(response, raw_refresh)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=token_expiry(days=7)))
    _set_refresh_cookie(response, raw_refresh)

    await log_action(db, action="user.login", user_id=user.id, resource_type="user", resource_id=user.id, request=request)
    return TokenResponse(access_token=access_token)


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = sha256(raw)
    now = datetime.now(UTC)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > now,
        )
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    rt.revoked = True
    new_raw, new_hash = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=new_hash, expires_at=token_expiry(days=7)))
    _set_refresh_cookie(response, new_raw)

    return TokenResponse(access_token=create_access_token(str(user.id), user.role))


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    raw = request.cookies.get(_REFRESH_COOKIE)
    if raw:
        token_hash = sha256(raw)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
    await log_action(db, action="user.logout", user_id=current_user.id, resource_type="user", resource_id=current_user.id, request=request)
    resp = Response(status_code=204)
    resp.delete_cookie(_REFRESH_COOKIE)
    return resp


# ── Get current user ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )


# ── Change own password ───────────────────────────────────────────────────────

@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    await log_action(db, action="user.password_changed", user_id=current_user.id, resource_type="user", resource_id=current_user.id, request=request)
    return Response(status_code=204)


# ── Issue SSE token ───────────────────────────────────────────────────────────

@router.post("/sse-token", response_model=SSETokenResponse)
async def issue_sse_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SSETokenResponse:
    raw, token_hash = generate_sse_token()
    db.add(SSEToken(user_id=current_user.id, token_hash=token_hash, expires_at=token_expiry(seconds=30)))
    return SSETokenResponse(sse_token=raw)
