from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from app.core.settings import settings

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


@dataclass
class RealtimeEvent:
    event_type: str
    trip_id: str
    payload: dict
    created_at: datetime


class RealtimeService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[RealtimeEvent] = []

    def publish_trip_event(self, *, event_type: str, trip_id: str, payload: dict) -> dict:
        event = RealtimeEvent(
            event_type=event_type,
            trip_id=trip_id,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self._events.append(event)
            if len(self._events) > 2000:
                self._events = self._events[-2000:]

        if settings.supabase_db_url and psycopg is not None:
            self._publish_postgres_notify(event)

        return self._serialize_event(event)

    def list_trip_events(self, *, trip_id: str, limit: int = 100) -> dict:
        with self._lock:
            rows = [e for e in self._events if e.trip_id == trip_id]
        rows = rows[-limit:]
        return {"events": [self._serialize_event(e) for e in rows]}

    def _publish_postgres_notify(self, event: RealtimeEvent) -> None:
        assert settings.supabase_db_url is not None
        payload = self._serialize_event(event)
        channel = f"trips:{event.trip_id}"

        with psycopg.connect(settings.supabase_db_url) as conn, conn.cursor() as cur:
            cur.execute("select pg_notify(%s, %s)", (channel, json.dumps(payload)))
            conn.commit()

    @staticmethod
    def _serialize_event(event: RealtimeEvent) -> dict:
        base = asdict(event)
        base["created_at"] = event.created_at.isoformat()
        return base


realtime_service = RealtimeService()
