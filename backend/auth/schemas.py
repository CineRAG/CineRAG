"""Pydantic schemas for auth and user endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: AuthUserResponse


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None = None
    created_at: datetime
