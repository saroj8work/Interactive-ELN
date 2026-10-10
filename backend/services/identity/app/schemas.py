from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
    owner_email: EmailStr
    owner_name: str = Field(min_length=1, max_length=160)


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    organization_slug: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    organization_slug: str = Field(min_length=1, max_length=80)
    email: EmailStr


class PasswordResetComplete(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 900


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    role: Literal["admin", "member"]
    is_active: bool
    email_verified_at: datetime
    created_at: datetime


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class CurrentUserRead(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    organization_id: int
    role: Literal["admin", "member"]
