"""Shared SQLAlchemy column helpers.

Models call these to keep cross-dialect column definitions in one place.
SQLite (tests) needs JSON in place of `text[]`; Postgres uses native
arrays. Both produce the same Python interface (a ``list[str]``).
"""

from sqlalchemy import JSON, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import ARRAY


def created_at_column() -> Column:
    """``timestamptz NOT NULL DEFAULT now()`` — matches the architecture doc."""
    return Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


def nullable_timestamp_column() -> Column:
    """``timestamptz NULL`` — for fields like ``last_seen_at`` and ``published_at``."""
    return Column(DateTime(timezone=True), nullable=True)


def tag_array_column() -> Column:
    """``text[]`` on Postgres, ``JSON`` on SQLite (tests)."""
    return Column(
        ARRAY(Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
