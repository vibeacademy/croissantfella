"""ModerationResult — append-only audit record of every moderation call.

``subject_type`` is ``'post'`` or ``'comment'``; ``subject_id`` references the
relevant table at the application layer (polymorphic; no DB-level FK so we
can audit calls for content that was later hard-deleted).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Column, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel

from app.models._columns import created_at_column


def _jsonb_column() -> Column:
    return Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)


def _categories_array_column() -> Column:
    return Column(
        ARRAY(Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
    )


class ModerationResult(SQLModel, table=True):
    __tablename__ = "moderation_results"
    __table_args__ = (Index("ix_moderation_results_subject", "subject_type", "subject_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    subject_type: str = Field(max_length=16)
    subject_id: uuid.UUID
    provider: str = Field(max_length=64)
    raw_response: dict = Field(default_factory=dict, sa_column=_jsonb_column())
    flagged: bool
    categories: list[str] = Field(default_factory=list, sa_column=_categories_array_column())
    max_score: Decimal = Field(sa_column=Column(Numeric(), nullable=False))
    decided_at: datetime | None = Field(default=None, sa_column=created_at_column())
