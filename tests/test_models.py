"""Model-level tests for the initial schema.

These cover the Definition of Done items from #10:

* every model can be inserted and queried via the test fixture
* the unique constraint on ``users.email`` raises on duplicate
* ``comments.parent_id`` cascades when its parent comment is deleted
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    Comment,
    ContentStatus,
    FormLength,
    Genre,
    MagicLinkToken,
    ModerationResult,
    ModerationSubject,
    Post,
    TasteProfile,
    Tone,
    User,
)


def _make_user(session: Session, email: str = "alice@example.com") -> User:
    user = User(email=email, display_name="Alice")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_user_insert_and_query(session: Session) -> None:
    user = _make_user(session)
    fetched = session.exec(select(User).where(User.email == "alice@example.com")).one()
    assert fetched.id == user.id
    assert fetched.display_name == "Alice"
    assert fetched.created_at is not None


def test_user_email_unique_constraint(session: Session) -> None:
    _make_user(session, email="dup@example.com")
    session.add(User(email="dup@example.com", display_name="Bob"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_taste_profile_round_trip(session: Session) -> None:
    user = _make_user(session)
    profile = TasteProfile(
        user_id=user.id,
        genres=[Genre.LITERARY.value, Genre.SCI_FI.value],
        tones=[Tone.CONTEMPLATIVE.value],
        form_lengths=[FormLength.SHORT_STORY.value],
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)

    fetched = session.exec(select(TasteProfile).where(TasteProfile.user_id == user.id)).one()
    assert fetched.genres == [Genre.LITERARY.value, Genre.SCI_FI.value]
    assert fetched.tones == [Tone.CONTEMPLATIVE.value]
    assert fetched.form_lengths == [FormLength.SHORT_STORY.value]


def test_post_insert_with_default_status(session: Session) -> None:
    user = _make_user(session)
    post = Post(
        author_id=user.id,
        title="A small thing",
        body="It begins...",
        genres=[Genre.LITERARY.value],
        tones=[Tone.CONTEMPLATIVE.value],
        form_length=FormLength.FLASH.value,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    assert post.status == ContentStatus.PENDING_MODERATION.value
    assert post.published_at is None


def test_comment_insert_and_query(session: Session) -> None:
    user = _make_user(session)
    post = Post(
        author_id=user.id,
        title="t",
        body="b",
        genres=[],
        tones=[],
        form_length=FormLength.FLASH.value,
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    comment = Comment(post_id=post.id, author_id=user.id, body="nice")
    session.add(comment)
    session.commit()
    session.refresh(comment)

    fetched = session.exec(select(Comment).where(Comment.post_id == post.id)).one()
    assert fetched.body == "nice"


def test_comment_parent_cascade_on_delete(session: Session) -> None:
    user = _make_user(session)
    post = Post(
        author_id=user.id,
        title="t",
        body="b",
        genres=[],
        tones=[],
        form_length=FormLength.FLASH.value,
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    parent = Comment(post_id=post.id, author_id=user.id, body="parent")
    session.add(parent)
    session.commit()
    session.refresh(parent)

    child = Comment(post_id=post.id, author_id=user.id, parent_id=parent.id, body="child")
    session.add(child)
    session.commit()
    child_id = child.id

    session.delete(parent)
    session.commit()

    assert session.get(Comment, parent.id) is None
    assert session.get(Comment, child_id) is None


def test_moderation_result_round_trip(session: Session) -> None:
    user = _make_user(session)
    post = Post(
        author_id=user.id,
        title="t",
        body="b",
        genres=[],
        tones=[],
        form_length=FormLength.FLASH.value,
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    result = ModerationResult(
        subject_type=ModerationSubject.POST.value,
        subject_id=post.id,
        provider="openai-moderation",
        raw_response={"id": "modr_x", "results": [{"flagged": False}]},
        flagged=False,
        categories=[],
        max_score=Decimal("0.01"),
    )
    session.add(result)
    session.commit()
    session.refresh(result)

    fetched = session.exec(
        select(ModerationResult).where(ModerationResult.subject_id == post.id)
    ).one()
    assert fetched.provider == "openai-moderation"
    assert fetched.raw_response["id"] == "modr_x"
    assert fetched.max_score == Decimal("0.01")


def test_magic_link_token_round_trip(session: Session) -> None:
    token = MagicLinkToken(
        email="alice@example.com",
        token_hash=b"\x00" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    session.add(token)
    session.commit()
    session.refresh(token)

    fetched = session.exec(
        select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com")
    ).one()
    assert fetched.token_hash == b"\x00" * 32
    assert fetched.consumed_at is None
    assert fetched.created_at is not None


def test_taste_profile_cascade_on_user_delete(session: Session) -> None:
    user = _make_user(session)
    profile = TasteProfile(
        user_id=user.id,
        genres=[Genre.LITERARY.value],
        tones=[Tone.CONTEMPLATIVE.value],
        form_lengths=[FormLength.FLASH.value],
    )
    session.add(profile)
    session.commit()
    profile_user_id = profile.user_id

    session.delete(user)
    session.commit()

    assert session.get(TasteProfile, profile_user_id) is None
