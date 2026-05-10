"""User and TasteProfile models."""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models._columns import (
    created_at_column,
    nullable_timestamp_column,
    tag_array_column,
)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=320)
    display_name: str = Field(max_length=100)
    bio: str | None = None
    created_at: datetime | None = Field(default=None, sa_column=created_at_column())
    last_seen_at: datetime | None = Field(default=None, sa_column=nullable_timestamp_column())


class TasteProfile(SQLModel, table=True):
    __tablename__ = "taste_profiles"

    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    genres: list[str] = Field(default_factory=list, sa_column=tag_array_column())
    tones: list[str] = Field(default_factory=list, sa_column=tag_array_column())
    form_lengths: list[str] = Field(default_factory=list, sa_column=tag_array_column())
    updated_at: datetime | None = Field(default=None, sa_column=created_at_column())
