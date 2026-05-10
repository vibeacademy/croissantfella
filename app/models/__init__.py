"""SQLModel database models.

Importing this package registers every table on ``SQLModel.metadata``,
which is what ``alembic/env.py`` and the test ``conftest`` rely on.
"""

from app.models.auth import MagicLinkToken
from app.models.moderation import ModerationResult
from app.models.post import Comment, Post
from app.models.taxonomy import (
    ContentStatus,
    FormLength,
    Genre,
    ModerationSubject,
    Tone,
)
from app.models.user import TasteProfile, User

__all__ = [
    "Comment",
    "ContentStatus",
    "FormLength",
    "Genre",
    "MagicLinkToken",
    "ModerationResult",
    "ModerationSubject",
    "Post",
    "TasteProfile",
    "Tone",
    "User",
]
