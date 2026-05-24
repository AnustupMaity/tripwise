from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.services.payment_service import payment_service

router = APIRouter()


class MarkPaymentRequest(BaseModel):
    trip_id: str
    actor_identifier: str
    from_member_id: str
    to_member_id: str
    amount: float = Field(gt=0)
    method: str


@router.get("/settlement")
def settlement(trip_id: str) -> dict:
    return payment_service.get_settlement(trip_id=trip_id)


@router.post("/mark-paid")
def mark_paid(payload: MarkPaymentRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    return payment_service.mark_paid(
        trip_id=payload.trip_id,
        actor_identifier=payload.actor_identifier,
        from_member_id=payload.from_member_id,
        to_member_id=payload.to_member_id,
        amount=payload.amount,
        method=payload.method,
    )


@router.get("/history")
def history(trip_id: str) -> dict:
    return payment_service.transaction_history(trip_id=trip_id)
