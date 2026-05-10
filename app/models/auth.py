"""MagicLinkToken — single-use sign-in token.

The raw token is never stored; only ``token_hash`` (sha256 of the raw bytes)
is persisted. Verification rehashes the incoming token and looks it up.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, Index, LargeBinary
from sqlmodel import Field, SQLModel

from app.models._columns import created_at_column, nullable_timestamp_column


class MagicLinkToken(SQLModel, table=True):
    __tablename__ = "magic_link_tokens"
    __table_args__ = (
        Index(
            "ix_magic_link_tokens_token_hash_unconsumed",
            "token_hash",
            unique=False,
            postgresql_where="consumed_at IS NULL",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=320, index=True)
    token_hash: bytes = Field(sa_column=Column(LargeBinary(), nullable=False))
    expires_at: datetime
    consumed_at: datetime | None = Field(default=None, sa_column=nullable_timestamp_column())
    created_at: datetime | None = Field(default=None, sa_column=created_at_column())
