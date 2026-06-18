from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token, sha256
from app.models.user import SSEToken, User

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_role(*roles: str):
    async def _check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _check


require_admin = require_role("admin")
require_editor_or_admin = require_role("editor", "admin")


async def validate_sse_token(
    token: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Validate a single-use SSE token from ?token= query param."""
    token_hash = sha256(token)
    now = datetime.now(UTC)

    result = await db.execute(
        select(SSEToken).where(
            SSEToken.token_hash == token_hash,
            SSEToken.used.is_(False),
            SSEToken.expires_at > now,
        )
    )
    sse_token = result.scalar_one_or_none()
    if sse_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSE_TOKEN_INVALID")

    sse_token.used = True
    await db.flush()

    result2 = await db.execute(select(User).where(User.id == sse_token.user_id))
    user = result2.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    return user
