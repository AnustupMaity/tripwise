from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.services.dispute_service import dispute_service

router = APIRouter()


class RaiseDisputeRequest(BaseModel):
    trip_id: str
    expense_id: str
    actor_identifier: str
    comment: str = Field(min_length=5)
    disputed_amount: float | None = None


class ReviewDisputeRequest(BaseModel):
    admin_identifier: str
    note: str | None = None


class ResolveDisputeRequest(BaseModel):
    admin_identifier: str
    resolution_comment: str = Field(min_length=3)


class AddDisputeCommentRequest(BaseModel):
    actor_identifier: str
    comment: str = Field(min_length=2)


@router.post("/")
def raise_dispute(payload: RaiseDisputeRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return dispute_service.raise_dispute(
            trip_id=payload.trip_id,
            expense_id=payload.expense_id,
            actor_identifier=payload.actor_identifier,
            comment=payload.comment,
            disputed_amount=payload.disputed_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/")
def list_disputes(trip_id: str) -> dict:
    return dispute_service.list_disputes(trip_id=trip_id)


@router.get("/{dispute_id}")
def get_dispute(dispute_id: str) -> dict:
    try:
        return dispute_service.get_dispute(dispute_id=dispute_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{dispute_id}/review")
def mark_under_review(dispute_id: str, payload: ReviewDisputeRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.admin_identifier, field_name="admin_identifier")
    try:
        return dispute_service.mark_under_review(
            dispute_id=dispute_id,
            admin_identifier=payload.admin_identifier,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, payload: ResolveDisputeRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.admin_identifier, field_name="admin_identifier")
    try:
        return dispute_service.resolve_dispute(
            dispute_id=dispute_id,
            admin_identifier=payload.admin_identifier,
            resolution_comment=payload.resolution_comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{dispute_id}/comments")
def add_comment(dispute_id: str, payload: AddDisputeCommentRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return dispute_service.add_comment(
            dispute_id=dispute_id,
            actor_identifier=payload.actor_identifier,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
