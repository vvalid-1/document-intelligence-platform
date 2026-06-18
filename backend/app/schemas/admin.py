from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


class AdminInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


class AdminInviteResponse(BaseModel):
    invitation_token: str
    email: str
    role: str
    expires_at: datetime


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class AdminUpdateRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|editor|viewer)$")


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
