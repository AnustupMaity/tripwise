from __future__ import annotations

from dataclasses import asdict

from app.services.dispute_store import build_dispute_store
from app.services.expense_service import expense_service
from app.services.in_app_notification_service import in_app_notification_service
from app.services.notification_templates import dispute_raised_template, dispute_resolved_template
from app.services.realtime_service import realtime_service
from app.services.trip_service import trip_service


class DisputeService:
    def __init__(self) -> None:
        self._store = build_dispute_store()

    def raise_dispute(self, *, trip_id: str, expense_id: str, actor_identifier: str, comment: str, disputed_amount: float | None) -> dict:
        if not trip_service.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        if len(comment.strip()) < 5:
            raise ValueError("dispute comment must be at least 5 characters")

        actor = trip_service.resolve_member_for_identifier(
            trip_id=trip_id,
            identifier=actor_identifier,
        )
        if actor is None:
            raise ValueError("actor is not a trip member")
        if actor["inviteStatus"] != "accepted":
            raise ValueError("only accepted members can raise disputes")
        if not actor["profileId"]:
            raise ValueError("member profile not found")

        expense = expense_service.get_expense(expense_id=expense_id)
        if expense is None:
            raise ValueError("expense not found")
        if expense.trip_id != trip_id:
            raise ValueError("expense does not belong to trip")
        if expense.status != "approved":
            raise ValueError("only approved expenses can be disputed")
        if disputed_amount is not None:
            if disputed_amount <= 0:
                raise ValueError("disputed amount must be greater than zero")
            if disputed_amount > float(expense.amount):
                raise ValueError("disputed amount cannot exceed expense amount")

        dispute = self._store.create_dispute(
            trip_id=trip_id,
            expense_id=expense_id,
            raised_by_profile_id=actor["profileId"],
            comment=comment.strip(),
            disputed_amount=disputed_amount,
        )

        self._store.add_dispute_comment(
            dispute_id=dispute.dispute_id,
            author_profile_id=actor["profileId"],
            comment=comment.strip(),
        )

        event = realtime_service.publish_trip_event(
            event_type="dispute_raised",
            trip_id=trip_id,
            payload={
                "disputeId": dispute.dispute_id,
                "expenseId": expense_id,
                "status": dispute.status,
            },
        )

        expense_label = (expense.description or expense.expense_id)[:60]
        title, message = dispute_raised_template(
            expense_label=expense_label,
            raised_by_name=actor_identifier,
        )
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=trip_id,
            event_type="dispute_raised",
            title=title,
            message=message,
            metadata={
                "disputeId": dispute.dispute_id,
                "expenseId": expense_id,
                "status": dispute.status,
            },
            exclude_member_ids={actor["memberId"]},
            send_whatsapp=True,
        )

        return {"dispute": asdict(dispute), "event": event, "notifications": notification_result}

    def list_disputes(self, *, trip_id: str) -> dict:
        disputes = self._store.list_disputes(trip_id=trip_id)
        return {"disputes": [asdict(d) for d in disputes]}

    def get_dispute(self, *, dispute_id: str) -> dict:
        dispute = self._store.get_dispute(dispute_id=dispute_id)
        if dispute is None:
            raise ValueError("dispute not found")
        comments = self._store.list_dispute_comments(dispute_id=dispute_id)
        return {
            "dispute": asdict(dispute),
            "comments": [asdict(c) for c in comments],
        }

    def mark_under_review(self, *, dispute_id: str, admin_identifier: str, note: str | None) -> dict:
        dispute = self._store.get_dispute(dispute_id=dispute_id)
        if dispute is None:
            raise ValueError("dispute not found")
        if not trip_service.is_trip_editable(trip_id=dispute.trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        admin = trip_service.resolve_member_for_identifier(
            trip_id=dispute.trip_id,
            identifier=admin_identifier,
        )
        if admin is None or admin["inviteStatus"] != "accepted" or admin["role"] != "admin":
            raise ValueError("only admin can review disputes")
        if not admin["profileId"]:
            raise ValueError("admin profile not found")

        updated = self._store.set_under_review(
            dispute_id=dispute_id,
            reviewer_profile_id=admin["profileId"],
        )

        if note and note.strip():
            self._store.add_dispute_comment(
                dispute_id=dispute_id,
                author_profile_id=admin["profileId"],
                comment=note.strip(),
            )

        event = realtime_service.publish_trip_event(
            event_type="dispute_in_review",
            trip_id=updated.trip_id,
            payload={"disputeId": updated.dispute_id, "status": updated.status},
        )

        return {"dispute": asdict(updated), "event": event}

    def resolve_dispute(self, *, dispute_id: str, admin_identifier: str, resolution_comment: str) -> dict:
        if len(resolution_comment.strip()) < 3:
            raise ValueError("resolution comment must be at least 3 characters")

        dispute = self._store.get_dispute(dispute_id=dispute_id)
        if dispute is None:
            raise ValueError("dispute not found")
        if not trip_service.is_trip_editable(trip_id=dispute.trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        admin = trip_service.resolve_member_for_identifier(
            trip_id=dispute.trip_id,
            identifier=admin_identifier,
        )
        if admin is None or admin["inviteStatus"] != "accepted" or admin["role"] != "admin":
            raise ValueError("only admin can resolve disputes")
        if not admin["profileId"]:
            raise ValueError("admin profile not found")

        updated = self._store.resolve_dispute(
            dispute_id=dispute_id,
            resolver_profile_id=admin["profileId"],
            resolution_comment=resolution_comment.strip(),
        )

        self._store.add_dispute_comment(
            dispute_id=dispute_id,
            author_profile_id=admin["profileId"],
            comment=f"Resolved: {resolution_comment.strip()}",
        )

        event = realtime_service.publish_trip_event(
            event_type="dispute_resolved",
            trip_id=updated.trip_id,
            payload={"disputeId": updated.dispute_id, "status": updated.status},
        )

        expense = expense_service.get_expense(expense_id=updated.expense_id)
        expense_label = (expense.description if expense else updated.expense_id)[:60]
        title, message = dispute_resolved_template(
            expense_label=expense_label,
            resolved_by_name=admin_identifier,
        )
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=updated.trip_id,
            event_type="dispute_resolved",
            title=title,
            message=message,
            metadata={
                "disputeId": updated.dispute_id,
                "expenseId": updated.expense_id,
                "status": updated.status,
                "resolutionComment": updated.resolution_comment,
            },
            exclude_member_ids={admin["memberId"]},
            send_whatsapp=True,
        )

        return {"dispute": asdict(updated), "event": event, "notifications": notification_result}

    def add_comment(self, *, dispute_id: str, actor_identifier: str, comment: str) -> dict:
        if len(comment.strip()) < 2:
            raise ValueError("comment must be at least 2 characters")

        dispute = self._store.get_dispute(dispute_id=dispute_id)
        if dispute is None:
            raise ValueError("dispute not found")
        if not trip_service.is_trip_editable(trip_id=dispute.trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        actor = trip_service.resolve_member_for_identifier(
            trip_id=dispute.trip_id,
            identifier=actor_identifier,
        )
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("only accepted members can comment")
        if not actor["profileId"]:
            raise ValueError("member profile not found")

        row = self._store.add_dispute_comment(
            dispute_id=dispute_id,
            author_profile_id=actor["profileId"],
            comment=comment.strip(),
        )
        event = realtime_service.publish_trip_event(
            event_type="dispute_comment_added",
            trip_id=dispute.trip_id,
            payload={"disputeId": dispute_id, "commentId": row.comment_id},
        )
        return {"comment": asdict(row), "event": event}

    def count_unresolved_disputes(self, *, trip_id: str) -> int:
        disputes = self._store.list_disputes(trip_id=trip_id)
        return len([d for d in disputes if d.status in {"open", "in_review"}])


dispute_service = DisputeService()
