from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from app.services.expense_store import build_expense_store
from app.services.in_app_notification_service import in_app_notification_service
from app.services.notification_templates import (
    expense_added_template,
    expense_approved_template,
    expense_rejected_template,
)
from app.services.realtime_service import realtime_service
from app.services.trip_service import trip_service

VALID_SPLIT_TYPES = {"equal", "unequal", "percentage", "selective", "custom"}


class ExpenseService:
    def __init__(self) -> None:
        self._store = build_expense_store()

    def add_expense(
        self,
        *,
        trip_id: str,
        actor_identifier: str,
        amount: float,
        description: str,
        split_type: str,
        paid_by: list[dict],
        splits: list[dict],
    ) -> dict:
        if not trip_service.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        if split_type not in VALID_SPLIT_TYPES:
            raise ValueError("invalid split type")

        actor = trip_service.resolve_member_for_identifier(
            trip_id=trip_id,
            identifier=actor_identifier,
        )
        if actor is None:
            raise ValueError("actor is not a trip member")
        if actor["inviteStatus"] != "accepted":
            raise ValueError("only accepted members can add expenses")
        if actor["role"] == "guest":
            raise ValueError("guest members cannot add expenses")
        if not actor["profileId"]:
            raise ValueError("member profile not found")

        eligible_member_ids = trip_service.split_eligible_member_ids(trip_id=trip_id)

        payer_rows = self._validate_and_build_payers(
            amount=amount,
            paid_by=paid_by,
            eligible_member_ids=eligible_member_ids,
        )
        split_rows = self._validate_and_build_splits(
            amount=amount,
            split_type=split_type,
            splits=splits,
            eligible_member_ids=eligible_member_ids,
        )

        auto_approved = actor["role"] == "admin"
        status = "approved" if auto_approved else "pending_approval"
        approved_by = actor["profileId"] if auto_approved else None
        approved_at = datetime.now(timezone.utc) if auto_approved else None

        expense = self._store.create_expense(
            trip_id=trip_id,
            amount=amount,
            description=description,
            split_type=split_type,
            status=status,
            created_by_profile_id=actor["profileId"],
            approved_by_profile_id=approved_by,
            approved_at=approved_at,
        )
        self._store.insert_payers(expense_id=expense.expense_id, payers=payer_rows)
        self._store.insert_splits(expense_id=expense.expense_id, splits=split_rows)

        event_type = "expense_approved" if status == "approved" else "expense_added"
        event = realtime_service.publish_trip_event(
            event_type=event_type,
            trip_id=trip_id,
            payload={
                "expenseId": expense.expense_id,
                "status": status,
                "amount": expense.amount,
                "splitType": expense.split_type,
            },
        )

        if status == "approved":
            title, message = expense_approved_template(
                amount=expense.amount,
                description=expense.description,
                approved_by_name=actor_identifier,
            )
            notify_event_type = "expense_approved"
        else:
            title, message = expense_added_template(
                amount=expense.amount,
                description=expense.description,
                added_by_name=actor_identifier,
            )
            notify_event_type = "expense_added"

        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=trip_id,
            event_type=notify_event_type,
            title=title,
            message=message,
            metadata={
                "expenseId": expense.expense_id,
                "status": status,
                "amount": expense.amount,
                "description": expense.description,
                "splitType": expense.split_type,
            },
            exclude_member_ids={actor["memberId"]},
            send_whatsapp=True,
        )

        return {
            "expense": asdict(expense),
            "approval": {
                "requiresAdminApproval": not auto_approved,
                "status": status,
            },
            "event": event,
            "notifications": notification_result,
        }

    def list_expenses(self, *, trip_id: str) -> dict:
        records = self._store.list_expenses(trip_id=trip_id)
        return {"expenses": [asdict(r) for r in records]}

    def get_expense(self, *, expense_id: str):
        return self._store.get_expense(expense_id=expense_id)

    def list_expense_payers(self, *, expense_id: str) -> list[dict]:
        rows = self._store.list_expense_payers(expense_id=expense_id)
        return [asdict(r) for r in rows]

    def list_expense_splits(self, *, expense_id: str) -> list[dict]:
        rows = self._store.list_expense_splits(expense_id=expense_id)
        return [asdict(r) for r in rows]

    def list_pending_approvals(self, *, trip_id: str, admin_identifier: str) -> dict:
        actor = trip_service.resolve_member_for_identifier(
            trip_id=trip_id,
            identifier=admin_identifier,
        )
        # If user is not a member or not accepted, return empty list (graceful fallback)
        if actor is None or actor["inviteStatus"] != "accepted":
            return {"pendingExpenses": []}
        # If not an admin, return empty list (authorization check)
        if actor["role"] != "admin":
            return {"pendingExpenses": []}

        records = self._store.list_expenses(trip_id=trip_id)
        pending = [asdict(r) for r in records if r.status == "pending_approval"]
        return {"pendingExpenses": pending}

    def approve_expense(self, *, expense_id: str, admin_identifier: str) -> dict:
        expense = self._store.get_expense(expense_id=expense_id)
        if expense is None:
            raise ValueError("expense not found")

        actor = trip_service.resolve_member_for_identifier(
            trip_id=expense.trip_id,
            identifier=admin_identifier,
        )
        if actor is None or actor["inviteStatus"] != "accepted" or actor["role"] != "admin":
            raise ValueError("only admin can approve expense")
        if not actor["profileId"]:
            raise ValueError("admin profile not found")
        if expense.status == "approved":
            return {"expense": asdict(expense), "status": expense.status}
        if expense.status != "pending_approval":
            raise ValueError("only pending expenses can be approved")

        updated = self._store.set_expense_status(
            expense_id=expense_id,
            status="approved",
            approved_by_profile_id=actor["profileId"],
            approved_at=datetime.now(timezone.utc),
        )
        event = realtime_service.publish_trip_event(
            event_type="expense_approved",
            trip_id=updated.trip_id,
            payload={"expenseId": updated.expense_id, "status": updated.status},
        )
        title, message = expense_approved_template(
            amount=updated.amount,
            description=updated.description,
            approved_by_name=admin_identifier,
        )
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=updated.trip_id,
            event_type="expense_approved",
            title=title,
            message=message,
            metadata={
                "expenseId": updated.expense_id,
                "status": updated.status,
                "amount": updated.amount,
                "description": updated.description,
            },
            exclude_member_ids={actor["memberId"]},
            send_whatsapp=True,
        )
        return {"expense": asdict(updated), "status": updated.status, "event": event, "notifications": notification_result}

    def reject_expense(self, *, expense_id: str, admin_identifier: str) -> dict:
        expense = self._store.get_expense(expense_id=expense_id)
        if expense is None:
            raise ValueError("expense not found")

        actor = trip_service.resolve_member_for_identifier(
            trip_id=expense.trip_id,
            identifier=admin_identifier,
        )
        if actor is None or actor["inviteStatus"] != "accepted" or actor["role"] != "admin":
            raise ValueError("only admin can reject expense")
        if expense.status != "pending_approval":
            raise ValueError("only pending expenses can be rejected")

        updated = self._store.set_expense_status(
            expense_id=expense_id,
            status="rejected",
            approved_by_profile_id=actor["profileId"],
            approved_at=datetime.now(timezone.utc),
        )
        event = realtime_service.publish_trip_event(
            event_type="expense_rejected",
            trip_id=updated.trip_id,
            payload={"expenseId": updated.expense_id, "status": updated.status},
        )
        title, message = expense_rejected_template(
            amount=updated.amount,
            description=updated.description,
            rejected_by_name=admin_identifier,
        )
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=updated.trip_id,
            event_type="expense_rejected",
            title=title,
            message=message,
            metadata={
                "expenseId": updated.expense_id,
                "status": updated.status,
                "amount": updated.amount,
                "description": updated.description,
            },
            exclude_member_ids={actor["memberId"]},
            send_whatsapp=True,
        )
        return {"expense": asdict(updated), "status": updated.status, "event": event, "notifications": notification_result}

    def _validate_and_build_payers(self, *, amount: float, paid_by: list[dict], eligible_member_ids: set[str]) -> list[tuple[str, float]]:
        if not paid_by:
            raise ValueError("paid_by cannot be empty")

        payer_rows: list[tuple[str, float]] = []
        total_paid = 0.0
        seen: set[str] = set()

        for payer in paid_by:
            member_id = str(payer.get("member_id", "")).strip()
            amount_paid = float(payer.get("amount_paid", 0))
            if not member_id:
                raise ValueError("payer member_id is required")
            if member_id not in eligible_member_ids:
                raise ValueError("payer must be an accepted member")
            if member_id in seen:
                raise ValueError("duplicate payer member_id")
            if amount_paid <= 0:
                raise ValueError("payer amount must be greater than zero")
            seen.add(member_id)
            payer_rows.append((member_id, round(amount_paid, 2)))
            total_paid += amount_paid

        if round(total_paid, 2) != round(amount, 2):
            raise ValueError("sum of payer amounts must equal expense amount")

        return payer_rows

    def _validate_and_build_splits(self, *, amount: float, split_type: str, splits: list[dict], eligible_member_ids: set[str]) -> list[tuple[str, float | None, float | None, bool]]:
        if split_type == "equal" and not splits:
            participants = sorted(eligible_member_ids)
            per_member = round(amount / len(participants), 2)
            rows = [(member_id, per_member, None, False) for member_id in participants]
            adjusted_total = round(sum(r[1] or 0 for r in rows), 2)
            drift = round(amount - adjusted_total, 2)
            if drift != 0 and rows:
                last = rows[-1]
                rows[-1] = (last[0], round((last[1] or 0) + drift, 2), None, False)
            return rows

        if not splits:
            raise ValueError("splits are required for selected split type")

        validated: list[tuple[str, float | None, float | None, bool]] = []
        participant_rows: list[tuple[str, float | None, float | None, bool]] = []
        seen: set[str] = set()

        for row in splits:
            member_id = str(row.get("member_id", "")).strip()
            if not member_id:
                raise ValueError("split member_id is required")
            if member_id in seen:
                raise ValueError("duplicate split member_id")
            if member_id not in eligible_member_ids:
                raise ValueError("split member must be an accepted member")
            seen.add(member_id)

            excluded = bool(row.get("excluded", False))
            amount_owed = float(row["amount_owed"]) if row.get("amount_owed") is not None else None
            percentage = float(row["percentage"]) if row.get("percentage") is not None else None

            record = (member_id, amount_owed, percentage, excluded)
            validated.append(record)
            if not excluded:
                participant_rows.append(record)

        if not participant_rows:
            raise ValueError("at least one non-excluded split participant is required")

        if split_type in {"unequal", "custom"}:
            total = round(sum((r[1] or 0) for r in participant_rows), 2)
            if total != round(amount, 2):
                raise ValueError("sum of split amounts must equal expense amount")
            for member_id, amount_owed, _, excluded in validated:
                if not excluded and (amount_owed is None or amount_owed < 0):
                    raise ValueError("amount_owed is required for non-excluded members")
            return validated

        if split_type == "percentage":
            total_percentage = round(sum((r[2] or 0) for r in participant_rows), 2)
            if total_percentage != 100.0:
                raise ValueError("sum of split percentages must be 100")

            rows: list[tuple[str, float | None, float | None, bool]] = []
            allocated = 0.0
            for idx, (member_id, _, percentage, excluded) in enumerate(validated):
                if excluded:
                    rows.append((member_id, 0.0, 0.0, True))
                    continue
                pct = float(percentage or 0)
                owed = round(amount * pct / 100.0, 2)
                allocated += owed
                if idx == len(validated) - 1:
                    owed = round(owed + (round(amount, 2) - round(allocated, 2)), 2)
                rows.append((member_id, owed, pct, False))
            return rows

        if split_type in {"equal", "selective"}:
            any_amounts = any(r[1] is not None for r in participant_rows)
            if any_amounts:
                total = round(sum((r[1] or 0) for r in participant_rows), 2)
                if total != round(amount, 2):
                    raise ValueError("sum of split amounts must equal expense amount")
                return validated

            participants = [r for r in validated if not r[3]]
            per_member = round(amount / len(participants), 2)
            rows: list[tuple[str, float | None, float | None, bool]] = []
            for member_id, _, _, excluded in validated:
                if excluded:
                    rows.append((member_id, 0.0, None, True))
                else:
                    rows.append((member_id, per_member, None, False))
            adjusted_total = round(sum((r[1] or 0) for r in rows), 2)
            drift = round(amount - adjusted_total, 2)
            if drift != 0:
                for idx in range(len(rows) - 1, -1, -1):
                    if not rows[idx][3]:
                        m, owed, pct, exc = rows[idx]
                        rows[idx] = (m, round((owed or 0) + drift, 2), pct, exc)
                        break
            return rows

        raise ValueError("unsupported split type")


expense_service = ExpenseService()
