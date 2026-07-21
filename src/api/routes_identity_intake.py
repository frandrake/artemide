"""Owner-only neutral person identity and separated intake-preview APIs."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field

from ..services import ServiceContext
from ..services.intake_service import IntakeService
from ..services.person_identity_service import PersonIdentityService
from .deps import require_owner

router = APIRouter(prefix="/api/v1", tags=["identity-intake"])


class PersonInput(BaseModel):
    display_name: str = Field(min_length=1)
    preferred_name: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    current_title: str | None = None
    current_organisation: str | None = None
    location: str | None = None
    source_url: str | None = None


class PersonPatch(BaseModel):
    display_name: str | None = None
    preferred_name: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    current_title: str | None = None
    current_organisation: str | None = None
    location: str | None = None
    source_url: str | None = None


class LinkInput(BaseModel):
    target_ulid: str = Field(min_length=1)


class PreviewInput(BaseModel):
    proposed_payload: dict[str, Any]
    provider: str
    model: str
    prompt: str
    input_hash: str
    sources: list[dict[str, Any]]
    provenance: dict[str, Any] = Field(default_factory=dict)


class ConfirmInput(BaseModel):
    corrected_payload: dict[str, Any] | None = None


class RejectInput(BaseModel):
    reason: str | None = None


@router.get("/people")
def list_people(ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.list(ctx)


@router.post("/people", status_code=status.HTTP_201_CREATED)
def create_person(body: PersonInput, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.create(ctx, **body.model_dump())


@router.get("/people/{person_ulid}")
def get_person(person_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.get_by_ulid(ctx, person_ulid)


@router.patch("/people/{person_ulid}")
def update_person(person_ulid: str, body: PersonPatch, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.update(ctx, person_ulid, **body.model_dump(exclude_unset=True))


@router.get("/people/{person_ulid}/links")
def get_person_links(person_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.get_links(ctx, person_ulid)


@router.post("/people/{person_ulid}/links/executive", status_code=status.HTTP_201_CREATED)
def link_executive(person_ulid: str, body: LinkInput, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.link_partner(ctx, person_ulid, body.target_ulid)


@router.post("/people/{person_ulid}/links/board", status_code=status.HTTP_201_CREATED)
def link_board(person_ulid: str, body: LinkInput, ctx: ServiceContext = Depends(require_owner)):
    return PersonIdentityService.link_board_contact(ctx, person_ulid, body.target_ulid)


@router.delete("/people/{person_ulid}/links/executive/{partner_ulid}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_executive(person_ulid: str, partner_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    PersonIdentityService.unlink_partner(ctx, person_ulid, partner_ulid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/people/{person_ulid}/links/board/{contact_ulid}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_board(person_ulid: str, contact_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    PersonIdentityService.unlink_board_contact(ctx, person_ulid, contact_ulid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _create_preview(domain: Literal["executive", "board"], ctx: ServiceContext, body: PreviewInput):
    method = IntakeService.create_executive_preview if domain == "executive" else IntakeService.create_board_preview
    return method(ctx, **body.model_dump())


def _list_previews(domain: Literal["executive", "board"], ctx: ServiceContext, state: str | None):
    method = IntakeService.list_executive_previews if domain == "executive" else IntakeService.list_board_previews
    return method(ctx, status=state)


def _get_preview(domain: Literal["executive", "board"], ctx: ServiceContext, ulid: str):
    method = IntakeService.get_executive_preview if domain == "executive" else IntakeService.get_board_preview
    return method(ctx, ulid)


@router.post("/intake/{domain}/previews", status_code=status.HTTP_201_CREATED)
def create_preview(domain: Literal["executive", "board"], body: PreviewInput, ctx: ServiceContext = Depends(require_owner)):
    return _create_preview(domain, ctx, body)


@router.get("/intake/{domain}/previews")
def list_previews(domain: Literal["executive", "board"], state: str | None = Query(default=None), ctx: ServiceContext = Depends(require_owner)):
    return _list_previews(domain, ctx, state)


@router.get("/intake/{domain}/previews/{preview_ulid}")
def get_preview(domain: Literal["executive", "board"], preview_ulid: str, ctx: ServiceContext = Depends(require_owner)):
    return _get_preview(domain, ctx, preview_ulid)


@router.post("/intake/{domain}/previews/{preview_ulid}/confirm")
def confirm_preview(domain: Literal["executive", "board"], preview_ulid: str, body: ConfirmInput, ctx: ServiceContext = Depends(require_owner)):
    method = IntakeService.confirm_executive_preview if domain == "executive" else IntakeService.confirm_board_preview
    return method(ctx, preview_ulid, corrected_payload=body.corrected_payload)


@router.post("/intake/{domain}/previews/{preview_ulid}/reject")
def reject_preview(domain: Literal["executive", "board"], preview_ulid: str, body: RejectInput, ctx: ServiceContext = Depends(require_owner)):
    method = IntakeService.reject_executive_preview if domain == "executive" else IntakeService.reject_board_preview
    return method(ctx, preview_ulid, reason=body.reason)
