from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.settings import settings
from app.services.trip_store import build_trip_store, normalize_member_identifier

try:
    import psycopg
    from psycopg.types.json import Json
except Exception:  # pragma: no cover
    psycopg = None
    Json = None


@dataclass
class InAppNotificationRecord:
    notification_id: str
    profile_id: str
    channel: str
    event_type: str
    payload: dict
    created_at: datetime
    delivered_at: datetime | None


class InMemoryInAppNotificationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: list[InAppNotificationRecord] = []

    def create(self, *, profile_id: str, event_type: str, payload: dict) -> InAppNotificationRecord:
        record = InAppNotificationRecord(
            notification_id=uuid4().hex,
            profile_id=profile_id,
            channel="in_app",
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(timezone.utc),
            delivered_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._rows.append(record)
            if len(self._rows) > 3000:
                self._rows = self._rows[-3000:]
        return record

    def list_for_profile(self, *, profile_id: str, limit: int) -> list[InAppNotificationRecord]:
        with self._lock:
            rows = [r for r in self._rows if r.profile_id == profile_id]
        return rows[-limit:]


class PostgresInAppNotificationStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def create(self, *, profile_id: str, event_type: str, payload: dict) -> InAppNotificationRecord:
        notification_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        delivered_at = created_at
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.notifications (id, profile_id, channel, event_type, payload, delivered_at, created_at)
                values (%s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (notification_id, profile_id, "in_app", event_type, Json(payload), delivered_at, created_at),
            )
            conn.commit()
        return InAppNotificationRecord(
            notification_id=notification_id,
            profile_id=profile_id,
            channel="in_app",
            event_type=event_type,
            payload=payload,
            created_at=created_at,
            delivered_at=delivered_at,
        )

    def list_for_profile(self, *, profile_id: str, limit: int) -> list[InAppNotificationRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, profile_id, channel, event_type, payload, created_at, delivered_at
                from public.notifications
                where profile_id = %s
                order by created_at desc
                limit %s
                """,
                (profile_id, limit),
            )
            rows = cur.fetchall()

        result: list[InAppNotificationRecord] = []
        for row in rows:
            result.append(
                InAppNotificationRecord(
                    notification_id=str(row[0]),
                    profile_id=str(row[1]),
                    channel=str(row[2]),
                    event_type=str(row[3]),
                    payload=dict(row[4] or {}),
                    created_at=row[5],
                    delivered_at=row[6],
                )
            )
        return result


def build_in_app_notification_store() -> InMemoryInAppNotificationStore | PostgresInAppNotificationStore:
    if settings.use_inmemory_stores:
        return InMemoryInAppNotificationStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresInAppNotificationStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory in-app notification store: %s", exc)
    return InMemoryInAppNotificationStore()


class InAppNotificationService:
    def __init__(self) -> None:
        self._store = build_in_app_notification_store()
        self._trip_store = build_trip_store()

    def notify_trip_members(
        self,
        *,
        trip_id: str,
        event_type: str,
        title: str,
        message: str,
        metadata: dict | None = None,
        exclude_member_ids: set[str] | None = None,
        send_whatsapp: bool = False,
        allowed_invite_statuses: set[str] | None = None,
    ) -> dict:
        excluded = exclude_member_ids or set()
        allowed_statuses = allowed_invite_statuses or {"accepted"}
        shared_payload = {
            "tripId": trip_id,
            "title": title,
            "message": message,
            "eventType": event_type,
            "metadata": metadata or {},
        }

        created: list[dict] = []
        members = self._trip_store.list_trip_members(trip_id=trip_id)
        for member in members:
            if member.member_id in excluded or member.invite_status not in allowed_statuses or not member.profile_id:
                continue
            result = self._notify_member(
                trip_id=trip_id,
                member_id=member.member_id,
                profile_id=member.profile_id,
                event_type=event_type,
                title=title,
                message=message,
                metadata=metadata,
                send_whatsapp=send_whatsapp,
            )
            if result:
                created.append(result["notification"])

        return {
            "created": created,
            "count": len(created),
        }

    def notify_trip_member(
        self,
        *,
        trip_id: str,
        member_id: str,
        event_type: str,
        title: str,
        message: str,
        metadata: dict | None = None,
        send_whatsapp: bool = False,
    ) -> dict:
        member = self._trip_store.get_trip_member(member_id=member_id)
        if member is None or member.trip_id != trip_id or not member.profile_id:
            return {"created": None, "whatsappJob": None}

        result = self._notify_member(
            trip_id=trip_id,
            member_id=member.member_id,
            profile_id=member.profile_id,
            event_type=event_type,
            title=title,
            message=message,
            metadata=metadata,
            send_whatsapp=send_whatsapp,
        )
        if not result:
            return {"created": None}

        return {
            "created": result["notification"],
        }

    def list_for_identifier(self, *, identifier: str, limit: int = 100) -> dict:
        normalized = normalize_member_identifier(identifier)
        profile = self._trip_store.find_profile_by_identifier(normalized)
        if not profile:
            return {"notifications": []}

        rows = self._store.list_for_profile(profile_id=profile.profile_id, limit=max(1, min(limit, 500)))
        return {"notifications": [self._serialize(row) for row in rows]}

    @staticmethod
    def _serialize(row: InAppNotificationRecord) -> dict:
        data = asdict(row)
        data["notification_id"] = row.notification_id
        data["created_at"] = row.created_at.isoformat()
        data["delivered_at"] = row.delivered_at.isoformat() if row.delivered_at else None
        return data

    def _notify_member(
        self,
        *,
        trip_id: str,
        member_id: str,
        profile_id: str,
        event_type: str,
        title: str,
        message: str,
        metadata: dict | None,
        send_whatsapp: bool,
    ) -> dict | None:
        payload = {
            "tripId": trip_id,
            "title": title,
            "message": message,
            "eventType": event_type,
            "metadata": metadata or {},
            "memberId": member_id,
        }
        record = self._store.create(profile_id=profile_id, event_type=event_type, payload=payload)
        result: dict = {"notification": self._serialize(record)}

        return result


in_app_notification_service = InAppNotificationService()
