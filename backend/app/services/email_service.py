from __future__ import annotations

import json
import re
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from app.core.settings import settings


class EmailService:
    def send_email(self, *, recipients: list[str], subject: str, html_content: str, attachment_path: str | None = None) -> dict:
        recipients = [r.strip().lower() for r in recipients if r.strip()]
        if not recipients:
            return {"sent": False, "reason": "no_recipients"}

        if not settings.brevo_api_key or not settings.brevo_sender_email:
            return {
                "sent": False,
                "reason": "brevo_not_configured",
                "recipients": recipients,
            }

        attachments = []
        if attachment_path:
            attachment_file = Path(attachment_path)
            if not attachment_file.exists():
                return {"sent": False, "reason": "attachment_not_found"}
            with attachment_file.open("rb") as f:
                content = f.read()
            import base64

            encoded = base64.b64encode(content).decode("utf-8")
            attachments.append(
                {
                    "name": attachment_file.name,
                    "content": encoded,
                }
            )

        sender_email = settings.brevo_sender_email.strip().lower()
        text_content = re.sub(r"<[^>]+>", " ", html_content)
        text_content = re.sub(r"\s+", " ", text_content).strip()

        payload = {
            "sender": {
                "email": sender_email,
                "name": settings.brevo_sender_name or "TripWise",
            },
            "to": [{"email": r} for r in recipients],
            "subject": subject,
            "htmlContent": html_content,
            "textContent": text_content,
        }
        if attachments:
            payload["attachment"] = attachments

        req = urlrequest.Request(
            url="https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": settings.brevo_api_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=30) as resp:
                status_code = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")
                if 200 <= status_code < 300:
                    return {"sent": True, "recipients": recipients, "provider": "brevo", "response": body}
                return {
                    "sent": False,
                    "reason": "brevo_error",
                    "statusCode": status_code,
                    "response": body,
                }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return {
                "sent": False,
                "reason": "brevo_error",
                "statusCode": exc.code,
                "response": body,
            }
        except URLError as exc:
            return {"sent": False, "reason": "network_error", "error": str(exc)}

    def send_otp_email(self, *, recipient: str, otp: str, purpose: str, expires_minutes: int) -> dict:
        subject = f"TripWise OTP for {purpose.title()}"
        html_content = (
            f"<p>Your TripWise OTP is <strong>{otp}</strong>.</p>"
            f"<p>It expires in {expires_minutes} minutes.</p>"
        )
        return self.send_email(recipients=[recipient], subject=subject, html_content=html_content)

    def send_report(self, *, recipients: list[str], subject: str, html_content: str, attachment_path: str) -> dict:
        return self.send_email(
            recipients=recipients,
            subject=subject,
            html_content=html_content,
            attachment_path=attachment_path,
        )


email_service = EmailService()
