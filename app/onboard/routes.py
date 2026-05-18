"""GET/POST /onboard — taste questionnaire form.

The verify endpoint (#13) redirects new users here; we close that loop
by rendering a form they can actually submit. POST validates every
submitted tag against the taxonomy enums (Genre / Tone / FormLength)
and UPSERTs a ``TasteProfile`` row keyed on ``user_id`` so a user can
edit their answers without duplicating rows.
"""

from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session

from app.auth.session import optional_current_user
from app.db import get_session
from app.models.taxonomy import FormLength, Genre, Tone
from app.models.user import TasteProfile, User
from app.templates import templates

router = APIRouter(tags=["onboard"])

SessionDep = Annotated[Session, Depends(get_session)]
MaybeUser = Annotated[User | None, Depends(optional_current_user)]


def _validate_tags(values: list[str], enum_type: type[StrEnum]) -> None:
    """Raise 422 if any element of ``values`` isn't a valid enum member.

    We keep the caller's original strings instead of coercing to the enum
    so what lands in the ``text[]`` column matches the enum's ``.value``.
    """
    valid = {member.value for member in enum_type}
    unknown = [v for v in values if v not in valid]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown {enum_type.__name__} values: {unknown}",
        )


@router.get("/onboard", response_class=HTMLResponse)
def onboard_form(request: Request, user: MaybeUser) -> Response:
    if user is None:
        return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "onboard/form.html",
        {"genres": list(Genre), "tones": list(Tone), "form_lengths": list(FormLength)},
    )


@router.post("/onboard")
def onboard_submit(
    request: Request,
    session: SessionDep,
    user: MaybeUser,
    genres: Annotated[list[str] | None, Form()] = None,
    tones: Annotated[list[str] | None, Form()] = None,
    form_lengths: Annotated[list[str] | None, Form()] = None,
) -> Response:
    if user is None:
        return RedirectResponse("/auth/login", status_code=302)

    genres = genres or []
    tones = tones or []
    form_lengths = form_lengths or []

    if not genres:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one genre is required",
        )

    _validate_tags(genres, Genre)
    _validate_tags(tones, Tone)
    _validate_tags(form_lengths, FormLength)

    # UPSERT: existing TasteProfile rows are updated in place so a user
    # editing their answers doesn't accumulate duplicate rows. The PK
    # is user_id (1:1 with users), so a SELECT-then-UPDATE-or-INSERT is
    # safe under sequential clicks.
    profile = session.get(TasteProfile, user.id)
    if profile is None:
        session.add(
            TasteProfile(
                user_id=user.id,
                genres=genres,
                tones=tones,
                form_lengths=form_lengths,
            )
        )
    else:
        profile.genres = genres
        profile.tones = tones
        profile.form_lengths = form_lengths
        session.add(profile)
    session.commit()

    return RedirectResponse("/", status_code=302)
