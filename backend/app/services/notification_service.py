from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from uuid import uuid4

from app.core.settings import settings
from app.services.email_service import email_service

Channel = Literal["email", "push"]
Status = Literal["queued", "retrying", "sent", "failed"]


@dataclass
class NotificationJob:
    job_id: str
    channel: Channel
    recipient: str
    subject: str | None
    message: str
    html_content: str | None
    attachment_path: str | None
    metadata: dict
    created_at: datetime
    next_attempt_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    status: Status = "queued"
    last_error: str | None = None
    sent_at: datetime | None = None


class NotificationService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: list[NotificationJob] = []
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run_worker, daemon=True, name="notification-worker")
        self._worker.start()

    def enqueue_email(
        self,
        *,
        recipient: str,
        subject: str,
        html_content: str,
        attachment_path: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return self._enqueue_job(
            channel="email",
            recipient=recipient,
            subject=subject,
            message="",
            html_content=html_content,
            attachment_path=attachment_path,
            metadata=metadata or {},
        )

    def enqueue_push(self, *, recipient: str, message: str, metadata: dict | None = None) -> dict:
        return self._enqueue_job(
            channel="push",
            recipient=recipient,
            subject=None,
            message=message,
            html_content=None,
            attachment_path=None,
            metadata=metadata or {},
        )

    def enqueue_otp(self, *, identifier: str, purpose: str, otp: str, expires_minutes: int) -> dict:
        subject = f"TripWise OTP for {purpose.title()}"
        html_content = (
            f"<p>Your TripWise OTP is <strong>{otp}</strong>.</p>"
            f"<p>It expires in {expires_minutes} minutes.</p>"
        )
        return self.enqueue_email(
            recipient=identifier,
            subject=subject,
            html_content=html_content,
            metadata={"kind": "otp", "purpose": purpose},
        )

    def list_jobs(self, *, limit: int = 200) -> dict:
        with self._lock:
            jobs = self._jobs[-limit:]
            return {"jobs": [asdict(j) for j in jobs]}

    def _enqueue_job(
        self,
        *,
        channel: Channel,
        recipient: str,
        subject: str | None,
        message: str,
        html_content: str | None,
        attachment_path: str | None,
        metadata: dict,
    ) -> dict:
        now = datetime.now(timezone.utc)
        job = NotificationJob(
            job_id=str(uuid4()),
            channel=channel,
            recipient=recipient.strip(),
            subject=subject,
            message=message,
            html_content=html_content,
            attachment_path=attachment_path,
            metadata=metadata,
            created_at=now,
            next_attempt_at=now,
            max_attempts=max(1, settings.notification_retry_max_attempts),
        )
        with self._lock:
            self._jobs.append(job)
        return {"queued": True, "jobId": job.job_id, "channel": channel, "recipient": job.recipient}

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            pending: list[NotificationJob] = []
            with self._lock:
                for job in self._jobs:
                    if job.status in {"queued", "retrying"} and job.next_attempt_at <= now:
                        pending.append(job)

            for job in pending:
                result = self._deliver(job)
                with self._lock:
                    if result.get("sent"):
                        job.status = "sent"
                        job.sent_at = datetime.now(timezone.utc)
                        job.last_error = None
                    else:
                        job.attempts += 1
                        job.last_error = str(result.get("reason") or result.get("error") or "delivery_failed")
                        if job.attempts >= job.max_attempts:
                            job.status = "failed"
                        else:
                            backoff = settings.notification_retry_base_delay_seconds * (2 ** (job.attempts - 1))
                            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
                            job.status = "retrying"

            self._stop_event.wait(1.0)

    def _deliver(self, job: NotificationJob) -> dict:
        if job.channel == "email":
            return email_service.send_email(
                recipients=[job.recipient],
                subject=job.subject or "TripWise Notification",
                html_content=job.html_content or f"<p>{job.message}</p>",
                attachment_path=job.attachment_path,
            )

        if job.channel == "push":
            return self._send_webhook(
                webhook_url=settings.push_webhook_url,
                payload={"recipient": job.recipient, "message": job.message, "metadata": job.metadata},
                reason_not_configured="push_not_configured",
            )

        return {"sent": False, "reason": "unsupported_channel"}

    def _send_webhook(self, *, webhook_url: str | None, payload: dict, reason_not_configured: str) -> dict:
        if not webhook_url:
            return {"sent": False, "reason": reason_not_configured}

        req = urlrequest.Request(
            url=webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlrequest.urlopen(req, timeout=20) as resp:
                status_code = resp.getcode()
                body = resp.read().decode("utf-8", errors="replace")
                if 200 <= status_code < 300:
                    return {"sent": True, "response": body}
                return {"sent": False, "reason": "webhook_error", "statusCode": status_code, "response": body}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return {"sent": False, "reason": "webhook_error", "statusCode": exc.code, "response": body}
        except URLError as exc:
            return {"sent": False, "reason": "network_error", "error": str(exc)}


notification_service = NotificationService()
