from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re
from uuid import uuid4

from app.core.settings import settings
from app.services.notification_service import notification_service
from app.services.expense_service import expense_service
from app.services.payment_service import payment_service
from app.services.realtime_service import realtime_service
from app.services.report_artifact_service import report_artifact_service
from app.services.report_store import build_report_store
from app.services.trip_service import trip_service

VALID_REPORT_TYPES = {"summary", "detailed", "settlement", "expense_breakdown"}
VALID_REPORT_FORMATS = {"pdf", "excel", "json"}
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReportService:
    def __init__(self) -> None:
        self._store = build_report_store()
        self._public_share_tokens: dict[str, dict] = {}

    def generate_report(self, *, trip_id: str, actor_identifier: str, report_type: str, format: str, email_to: list[str] | None) -> dict:
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError("invalid report_type")
        if format not in VALID_REPORT_FORMATS:
            raise ValueError("invalid format")

        actor = trip_service.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")

        settlement = payment_service.get_settlement(trip_id=trip_id)
        report_id = str(uuid4())
        artifact_payload = {
            "tripId": trip_id,
            "reportType": report_type,
            "generatedByMemberId": actor["memberId"],
            **settlement,
        }
        artifact_path, report_url = report_artifact_service.generate(
            report_id=report_id,
            trip_id=trip_id,
            report_type=report_type,
            format=format,
            payload=artifact_payload,
        )

        record = self._store.create_report(
            report_id=report_id,
            trip_id=trip_id,
            generated_by_member_id=actor["memberId"],
            report_type=report_type,
            format=format,
            file_url=report_url,
            emailed_to=[],
        )

        email_result = {"sent": False, "reason": "not_requested"}
        if email_to:
            recipients = normalize_recipient_list(email_to)
            for recipient in recipients:
                notification_service.enqueue_email(
                    recipient=recipient,
                    subject=f"TripWise {report_type.title()} Report for Trip {trip_id}",
                    html_content=f"<p>Your report is ready.</p><p>Download link: <a href=\"{report_url}\">{report_url}</a></p>",
                    attachment_path=artifact_path,
                    metadata={"kind": "report", "reportId": record.report_id, "tripId": trip_id},
                )
            self._store.append_emailed_to(report_id=record.report_id, recipients=recipients)
            email_result = {"queued": True, "recipients": recipients, "provider": "notification_queue"}

        event = realtime_service.publish_trip_event(
            event_type="report_generated",
            trip_id=trip_id,
            payload={
                "reportId": record.report_id,
                "reportType": record.report_type,
                "format": record.format,
                "emailSent": email_result.get("sent", False),
            },
        )

        return {
            "report": asdict(record),
            "settlementSnapshot": settlement,
            "emailDelivery": email_result,
            "event": event,
        }

    def list_reports(self, *, trip_id: str) -> dict:
        records = self._store.list_reports(trip_id=trip_id)
        return {"reports": [asdict(r) for r in records]}

    def send_report_email(self, *, trip_id: str, report_id: str, actor_identifier: str, recipients: list[str]) -> dict:
        actor = trip_service.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")

        normalized_recipients = normalize_recipient_list(recipients)
        if not normalized_recipients:
            raise ValueError("at least one recipient is required")

        report = self._store.get_report(report_id=report_id)
        if report is None or report.trip_id != trip_id:
            raise ValueError("report not found")

        filename = Path(report.file_url).name
        attachment_path = str(Path(settings.report_output_dir) / filename)
        for recipient in normalized_recipients:
            notification_service.enqueue_email(
                recipient=recipient,
                subject=f"TripWise {report.report_type.title()} Report for Trip {trip_id}",
                html_content=f"<p>Your report is ready.</p><p>Download link: <a href=\"{report.file_url}\">{report.file_url}</a></p>",
                attachment_path=attachment_path,
                metadata={"kind": "report", "reportId": report_id, "tripId": trip_id},
            )
        updated = self._store.append_emailed_to(report_id=report_id, recipients=normalized_recipients)
        if updated is not None:
            report = updated
        email_result = {"queued": True, "recipients": normalized_recipients, "provider": "notification_queue"}

        event = realtime_service.publish_trip_event(
            event_type="report_emailed",
            trip_id=trip_id,
            payload={
                "reportId": report_id,
                "sent": email_result.get("sent", False),
                "recipients": normalized_recipients,
            },
        )

        return {
            "report": asdict(report),
            "emailDelivery": email_result,
            "event": event,
        }

    def create_public_summary_link(self, *, trip_id: str, actor_identifier: str) -> dict:
        actor = trip_service.resolve_member_for_identifier(trip_id=trip_id, identifier=actor_identifier)
        if actor is None or actor["inviteStatus"] != "accepted":
            raise ValueError("actor is not an accepted trip member")
        token = str(uuid4())
        self._public_share_tokens[token] = {"trip_id": trip_id}
        return {"token": token, "url": f"/api/v1/reports/public/summary/{token}"}

    def get_public_summary(self, *, token: str) -> dict:
        link = self._public_share_tokens.get(token)
        if not link:
            raise ValueError("invalid or expired share link")
        trip_id = str(link["trip_id"])
        settlement = payment_service.get_settlement(trip_id=trip_id)
        expenses = expense_service.list_expenses(trip_id=trip_id)["expenses"]
        return {
            "tripId": trip_id,
            "readOnly": True,
            "expenseCount": len(expenses),
            "totalExpense": round(sum(float(item["amount"]) for item in expenses), 2),
            "approvedExpenseCount": len([item for item in expenses if item["status"] == "approved"]),
            "settlement": settlement,
        }


report_service = ReportService()


def normalize_recipient_list(recipients: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in recipients:
        email = value.strip().lower()
        if not email:
            continue
        if not EMAIL_REGEX.match(email):
            raise ValueError(f"invalid email recipient: {value}")
        if email in seen:
            continue
        seen.add(email)
        normalized.append(email)
    return normalized
