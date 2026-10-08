from __future__ import annotations

from pydantic import BaseModel, Field


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class CredentialsUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=6, max_length=128)
