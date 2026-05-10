"""Post and Comment models.

Comments support one level of nesting (``parent_id`` may reference another
comment, but a comment with a non-null ``parent_id`` may not itself be
replied to). The depth invariant is enforced at the application layer —
the schema only enforces the FK relationship.
"""

import uuid
from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.models._columns import (
    created_at_column,
    nullable_timestamp_column,
    tag_array_column,
)
from app.models.taxonomy import ContentStatus


class Post(SQLModel, table=True):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_status_published_at", "status", "published_at"),
        Index("ix_posts_genres_gin", "genres", postgresql_using="gin"),
        Index("ix_posts_tones_gin", "tones", postgresql_using="gin"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    author_id: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        index=True,
    )
    title: str = Field(max_length=200)
    body: str
    genres: list[str] = Field(default_factory=list, sa_column=tag_array_column())
    tones: list[str] = Field(default_factory=list, sa_column=tag_array_column())
    form_length: str = Field(max_length=32)
    status: str = Field(default=ContentStatus.PENDING_MODERATION.value, max_length=32)
    created_at: datetime | None = Field(default=None, sa_column=created_at_column())
    published_at: datetime | None = Field(default=None, sa_column=nullable_timestamp_column())


class Comment(SQLModel, table=True):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_post_status_created", "post_id", "status", "created_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    post_id: uuid.UUID = Field(
        foreign_key="posts.id",
        ondelete="CASCADE",
        index=True,
    )
    author_id: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="CASCADE",
        index=True,
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="comments.id",
        ondelete="CASCADE",
        index=True,
    )
    body: str
    status: str = Field(default=ContentStatus.PENDING_MODERATION.value, max_length=32)
    created_at: datetime | None = Field(default=None, sa_column=created_at_column())
    published_at: datetime | None = Field(default=None, sa_column=nullable_timestamp_column())
