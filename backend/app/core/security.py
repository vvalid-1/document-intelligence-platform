from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

_BCRYPT_ROUNDS = 12


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


# ── Refresh tokens (opaque random) ───────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Store only the hash."""
    raw = secrets.token_hex(64)
    return raw, _sha256(raw)


# ── SSE tokens (short-lived single-use) ──────────────────────────────────────

def generate_sse_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). 30-character URL-safe token."""
    raw = secrets.token_urlsafe(22)[:30]
    return raw, _sha256(raw)


# ── Shared ────────────────────────────────────────────────────────────────────

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha256(value: str) -> str:
    return _sha256(value)


def token_expiry(days: int = 0, minutes: int = 0, seconds: int = 0) -> datetime:
    return datetime.now(UTC) + timedelta(days=days, minutes=minutes, seconds=seconds)
