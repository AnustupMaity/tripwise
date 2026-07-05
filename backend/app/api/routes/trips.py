from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from cachetools import TTLCache, cached

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.services.payment_service import payment_service
from app.services.trip_service import trip_service

router = APIRouter()

# Caches for read-heavy operations
trip_list_cache = TTLCache(maxsize=1000, ttl=300)
trip_member_cache = TTLCache(maxsize=1000, ttl=300)


class CreateTripRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    creator_identifier: str
    creator_name: str | None = None
    member_identifiers: list[str] = Field(default_factory=list)
    creation_mode: Literal["self", "dynamic"] = "dynamic"
    member_entries: list[dict] = Field(default_factory=list)


class InviteMemberRequest(BaseModel):
    identifier: str
    actor_identifier: str | None = None


class InviteAllMembersRequest(BaseModel):
    identifiers: list[str] = Field(default_factory=list)
    actor_identifier: str | None = None


class RespondInviteRequest(BaseModel):
    action: Literal["accepted", "rejected"]
    actor_identifier: str | None = None


class TripLifecycleRequest(BaseModel):
    actor_identifier: str


class UpdateTripRequest(BaseModel):
    actor_identifier: str
    name: str = Field(min_length=2, max_length=120)


class UpdateMemberRoleRequest(BaseModel):
    actor_identifier: str
    role: Literal["admin", "member", "guest"]


@router.post("/")
def create_trip(payload: CreateTripRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.creator_identifier, field_name="creator_identifier")
    try:
        result = trip_service.create_trip(
            trip_name=payload.name,
            creator_identifier=payload.creator_identifier,
            creator_name=payload.creator_name,
            member_identifiers=payload.member_identifiers,
            creation_mode=payload.creation_mode,
            member_entries=payload.member_entries,
        )
        trip_list_cache.clear()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/")
@cached(cache=trip_list_cache)
def list_trips(creator_identifier: str | None = None, principal: SessionPrincipal = Depends(require_session)) -> dict:
    identifier = creator_identifier.strip() if creator_identifier else principal.email
    ensure_identifier_matches(principal, identifier, field_name="creator_identifier")
    return trip_service.list_trips(creator_identifier=identifier)


@router.get("/{trip_id}/members")
@cached(cache=trip_member_cache)
def list_trip_members(trip_id: str) -> dict:
    return trip_service.list_members(trip_id=trip_id)


@router.patch("/{trip_id}")
def update_trip(trip_id: str, payload: UpdateTripRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.rename_trip(
            trip_id=trip_id,
            actor_identifier=payload.actor_identifier,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{trip_id}/members/eligible")
def list_split_eligible_members(trip_id: str) -> dict:
    return trip_service.list_split_eligible_members(trip_id=trip_id)


@router.post("/{trip_id}/members/invite")
def invite_member(trip_id: str, payload: InviteMemberRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    actor_identifier = payload.actor_identifier or principal.email
    ensure_identifier_matches(principal, actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.invite_member(
            trip_id=trip_id,
            identifier=payload.identifier,
            actor_identifier=actor_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{trip_id}/members/invite-all")
def invite_all_members(trip_id: str, payload: InviteAllMembersRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    actor_identifier = payload.actor_identifier or principal.email
    ensure_identifier_matches(principal, actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.invite_all_members(
            trip_id=trip_id,
            identifiers=payload.identifiers,
            actor_identifier=actor_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/members/{member_id}/respond")
def respond_invite(member_id: str, payload: RespondInviteRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    actor_identifier = payload.actor_identifier or principal.email
    ensure_identifier_matches(principal, actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.respond_invite(
            member_id=member_id,
            action=payload.action,
            actor_identifier=actor_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/members/{member_id}/reinvite")
def reinvite_member(member_id: str, principal: SessionPrincipal = Depends(require_session)) -> dict:
    try:
        return trip_service.reinvite_member(
            member_id=member_id,
            actor_identifier=principal.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/members/{member_id}")
def remove_member(member_id: str, principal: SessionPrincipal = Depends(require_session)) -> dict:
    try:
        return trip_service.remove_member(
            member_id=member_id,
            actor_identifier=principal.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/members/{member_id}/role")
def update_member_role(member_id: str, payload: UpdateMemberRoleRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.update_member_role(
            member_id=member_id,
            actor_identifier=payload.actor_identifier,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{trip_id}/close")
def close_trip(trip_id: str, payload: TripLifecycleRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        result = trip_service.close_trip(
            trip_id=trip_id,
            actor_identifier=payload.actor_identifier,
        )
        result["settlement"] = payment_service.get_settlement(trip_id=trip_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{trip_id}/archive")
def archive_trip(trip_id: str, payload: TripLifecycleRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return trip_service.move_trip_to_past(
            trip_id=trip_id,
            actor_identifier=payload.actor_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
