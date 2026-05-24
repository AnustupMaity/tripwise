from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from app.services.dispute_service import dispute_service
from app.services.expense_service import expense_service
from app.services.in_app_notification_service import in_app_notification_service
from app.services.payment_store import build_payment_store
from app.services.realtime_service import realtime_service
from app.services.trip_service import trip_service

PAYMENT_METHODS = {"bank", "cash", "manual"}


class PaymentService:
    def __init__(self) -> None:
        self._store = build_payment_store()

    def get_settlement(self, *, trip_id: str) -> dict:
        blocking = dispute_service.count_unresolved_disputes(trip_id=trip_id)
        approved_expenses = [e for e in expense_service.list_expenses(trip_id=trip_id)["expenses"] if e["status"] == "approved"]

        if not approved_expenses:
            return {
                "tripId": trip_id,
                "blockedByUnresolvedDisputes": blocking > 0,
                "unresolvedDisputeCount": blocking,
                "whoOwesWhom": [],
                "memberBalances": {},
            }

        pairwise = self._build_pairwise_obligations(trip_id=trip_id, approved_expenses=approved_expenses)
        net_balances = self._collapse_to_net_balances(pairwise)
        recommended = self._minimize_transactions(net_balances)

        return {
            "tripId": trip_id,
            "blockedByUnresolvedDisputes": blocking > 0,
            "unresolvedDisputeCount": blocking,
            "whoOwesWhom": recommended,
            "memberBalances": {k: round(v, 2) for k, v in net_balances.items()},
        }

    def mark_paid(self, *, trip_id: str, actor_identifier: str, from_member_id: str, to_member_id: str, amount: float, method: str) -> dict:
        if not trip_service.is_trip_editable(trip_id=trip_id):
            raise ValueError("trip is closed and no edits are allowed")

        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        if method not in PAYMENT_METHODS:
            raise ValueError("invalid payment method")

        actor = trip_service.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")

        from_member = trip_service.get_member(member_id=from_member_id)
        to_member = trip_service.get_member(member_id=to_member_id)
        if from_member is None or to_member is None:
            raise ValueError("payment members not found")
        if from_member["tripId"] != trip_id or to_member["tripId"] != trip_id:
            raise ValueError("payment members do not belong to trip")

        if actor["memberId"] not in {from_member_id, to_member_id} and actor["role"] != "admin":
            raise ValueError("actor must be payer, payee, or admin")

        payment = self._store.create_payment(
            trip_id=trip_id,
            from_member_id=from_member_id,
            to_member_id=to_member_id,
            amount=round(amount, 2),
            method=method,
            status="paid",
            paid_at=datetime.now(timezone.utc),
        )

        event = realtime_service.publish_trip_event(
            event_type="payment_marked_paid",
            trip_id=trip_id,
            payload={
                "paymentId": payment.payment_id,
                "fromMemberId": payment.from_member_id,
                "toMemberId": payment.to_member_id,
                "amount": payment.amount,
                "method": payment.method,
            },
        )

        from_label = (from_member.get("identifier") or from_member.get("memberId") or "member")[:24]
        to_label = (to_member.get("identifier") or to_member.get("memberId") or "member")[:24]
        notification_result = in_app_notification_service.notify_trip_members(
            trip_id=trip_id,
            event_type="payment_marked_paid",
            title="Payment settled",
            message=f"{from_label} paid {to_label} Rs {payment.amount:.2f} via {payment.method}.",
            metadata={
                "paymentId": payment.payment_id,
                "fromMemberId": payment.from_member_id,
                "toMemberId": payment.to_member_id,
                "amount": payment.amount,
                "method": payment.method,
            },
            exclude_member_ids={actor["memberId"]},
            send_whatsapp=True,
        )

        return {
            "payment": asdict(payment),
            "event": event,
            "notifications": notification_result,
        }

    def transaction_history(self, *, trip_id: str) -> dict:
        rows = self._store.list_payments(trip_id=trip_id)
        return {"transactions": [asdict(r) for r in rows]}

    def _build_pairwise_obligations(self, *, trip_id: str, approved_expenses: list[dict]) -> list[dict]:
        obligations: list[dict] = []

        for expense in approved_expenses:
            expense_id = expense["expense_id"]
            payers = expense_service.list_expense_payers(expense_id=expense_id)
            splits = [s for s in expense_service.list_expense_splits(expense_id=expense_id) if not s["excluded"]]
            total_paid = sum(float(p["amount_paid"]) for p in payers)
            if total_paid <= 0:
                continue

            for split in splits:
                debtor_member_id = split["member_id"]
                owed = float(split["amount_owed"] or 0)
                if owed <= 0:
                    continue

                for payer in payers:
                    creditor_member_id = payer["member_id"]
                    if creditor_member_id == debtor_member_id:
                        continue
                    ratio = float(payer["amount_paid"]) / total_paid
                    amount = round(owed * ratio, 2)
                    if amount <= 0:
                        continue
                    obligations.append(
                        {
                            "fromMemberId": debtor_member_id,
                            "toMemberId": creditor_member_id,
                            "amount": amount,
                        }
                    )

        return self._consolidate_pairwise(obligations)

    def _consolidate_pairwise(self, obligations: list[dict]) -> list[dict]:
        grouped: dict[tuple[str, str], float] = {}
        for row in obligations:
            key = (row["fromMemberId"], row["toMemberId"])
            grouped[key] = grouped.get(key, 0.0) + float(row["amount"])
        result = []
        for (debtor, creditor), amount in grouped.items():
            if round(amount, 2) > 0:
                result.append({"fromMemberId": debtor, "toMemberId": creditor, "amount": round(amount, 2)})
        return result

    def _collapse_to_net_balances(self, obligations: list[dict]) -> dict[str, float]:
        balances: dict[str, float] = {}
        for row in obligations:
            debtor = row["fromMemberId"]
            creditor = row["toMemberId"]
            amount = float(row["amount"])
            balances[debtor] = balances.get(debtor, 0.0) - amount
            balances[creditor] = balances.get(creditor, 0.0) + amount
        return balances

    def _minimize_transactions(self, balances: dict[str, float]) -> list[dict]:
        debtors = [[member_id, -amt] for member_id, amt in balances.items() if amt < -0.01]
        creditors = [[member_id, amt] for member_id, amt in balances.items() if amt > 0.01]
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)

        i, j = 0, 0
        transfers: list[dict] = []
        while i < len(debtors) and j < len(creditors):
            debtor_id, debt = debtors[i]
            creditor_id, credit = creditors[j]
            amount = round(min(debt, credit), 2)
            if amount > 0:
                transfers.append(
                    {
                        "fromMemberId": debtor_id,
                        "toMemberId": creditor_id,
                        "amount": amount,
                    }
                )
            debtors[i][1] = round(debt - amount, 2)
            creditors[j][1] = round(credit - amount, 2)

            if debtors[i][1] <= 0.01:
                i += 1
            if creditors[j][1] <= 0.01:
                j += 1

        return transfers


payment_service = PaymentService()
