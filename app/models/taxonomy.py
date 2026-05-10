"""Tag taxonomy and content lifecycle enums.

Tag values are validated at the application layer rather than enforced
via a DB taxonomy table — see ADR-003 in docs/TECHNICAL-ARCHITECTURE.md
and the "Tag taxonomy is fixed" guardrail in CLAUDE.md.
"""

from enum import StrEnum


class Genre(StrEnum):
    LITERARY = "literary"
    SCI_FI = "sci_fi"
    FANTASY = "fantasy"
    HORROR = "horror"
    ROMANCE = "romance"
    MYSTERY = "mystery"
    POETRY = "poetry"
    ESSAY = "essay"
    MEMOIR = "memoir"
    SCREENPLAY = "screenplay"
    FANFIC = "fanfic"
    OTHER = "other"


class Tone(StrEnum):
    DARK = "dark"
    COMEDIC = "comedic"
    CONTEMPLATIVE = "contemplative"
    ACTION = "action"
    ROMANTIC = "romantic"
    EXPERIMENTAL = "experimental"


class FormLength(StrEnum):
    FLASH = "flash"
    SHORT_STORY = "short_story"
    NOVELLA_CHAPTER = "novella_chapter"
    NOVEL_CHAPTER = "novel_chapter"
    SERIAL = "serial"
    POEM = "poem"


class ContentStatus(StrEnum):
    PENDING_MODERATION = "pending_moderation"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class ModerationSubject(StrEnum):
    POST = "post"
    COMMENT = "comment"
