from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.services.expense_service import expense_service

router = APIRouter()


class ExpensePayerInput(BaseModel):
    member_id: str
    amount_paid: float = Field(gt=0)


class ExpenseSplitInput(BaseModel):
    member_id: str
    amount_owed: float | None = None
    percentage: float | None = None
    excluded: bool = False


class AddExpenseRequest(BaseModel):
    trip_id: str
    actor_identifier: str
    amount: float = Field(gt=0)
    description: str
    paid_by: list[ExpensePayerInput]
    split_type: str
    splits: list[ExpenseSplitInput] = Field(default_factory=list)


class ExpenseApprovalActionRequest(BaseModel):
    admin_identifier: str


@router.post("/")
def add_expense(payload: AddExpenseRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    return expense_service.add_expense(
        trip_id=payload.trip_id,
        actor_identifier=payload.actor_identifier,
        amount=payload.amount,
        description=payload.description,
        split_type=payload.split_type,
        paid_by=[p.model_dump() for p in payload.paid_by],
        splits=[s.model_dump() for s in payload.splits],
    )


@router.get("/")
def list_expenses(trip_id: str) -> dict:
    return expense_service.list_expenses(trip_id=trip_id)


@router.get("/pending")
def list_pending_approvals(trip_id: str, admin_identifier: str, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, admin_identifier, field_name="admin_identifier")
    return expense_service.list_pending_approvals(
        trip_id=trip_id,
        admin_identifier=admin_identifier,
    )


@router.post("/{expense_id}/approve")
def approve_expense(expense_id: str, payload: ExpenseApprovalActionRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.admin_identifier, field_name="admin_identifier")
    return expense_service.approve_expense(
        expense_id=expense_id,
        admin_identifier=payload.admin_identifier,
    )


@router.post("/{expense_id}/reject")
def reject_expense(expense_id: str, payload: ExpenseApprovalActionRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.admin_identifier, field_name="admin_identifier")
    return expense_service.reject_expense(
        expense_id=expense_id,
        admin_identifier=payload.admin_identifier,
    )
