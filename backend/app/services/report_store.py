from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.settings import settings

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


@dataclass
class ReportRecord:
    report_id: str
    trip_id: str
    generated_by_member_id: str
    report_type: str
    format: str
    file_url: str
    emailed_to: list[str]
    created_at: datetime
    expires_at: datetime


class InMemoryReportStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: dict[str, ReportRecord] = {}

    def create_report(self, *, report_id: str | None = None, trip_id: str, generated_by_member_id: str, report_type: str, format: str, file_url: str, emailed_to: list[str]) -> ReportRecord:
        with self._lock:
            now = datetime.now(timezone.utc)
            record = ReportRecord(
                report_id=report_id or uuid4().hex,
                trip_id=trip_id,
                generated_by_member_id=generated_by_member_id,
                report_type=report_type,
                format=format,
                file_url=file_url,
                emailed_to=emailed_to,
                created_at=now,
                expires_at=now + timedelta(days=30),
            )
            self._reports[record.report_id] = record
            return record

    def list_reports(self, *, trip_id: str) -> list[ReportRecord]:
        with self._lock:
            return [r for r in self._reports.values() if r.trip_id == trip_id]

    def get_report(self, *, report_id: str) -> ReportRecord | None:
        with self._lock:
            return self._reports.get(report_id)

    def append_emailed_to(self, *, report_id: str, recipients: list[str]) -> ReportRecord | None:
        with self._lock:
            record = self._reports.get(report_id)
            if record is None:
                return None
            merged = list(dict.fromkeys([*record.emailed_to, *recipients]))
            record.emailed_to = merged
            self._reports[report_id] = record
            return record


class PostgresReportStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def create_report(self, *, report_id: str | None = None, trip_id: str, generated_by_member_id: str, report_type: str, format: str, file_url: str, emailed_to: list[str]) -> ReportRecord:
        resolved_report_id = report_id or str(uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.reports (id, trip_id, generated_by, report_type, format, file_url, email_sent_to, created_at, expires_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (resolved_report_id, trip_id, generated_by_member_id, report_type, format, file_url, ",".join(emailed_to), now, expires_at),
            )
            conn.commit()
        return ReportRecord(
            report_id=resolved_report_id,
            trip_id=trip_id,
            generated_by_member_id=generated_by_member_id,
            report_type=report_type,
            format=format,
            file_url=file_url,
            emailed_to=emailed_to,
            created_at=now,
            expires_at=expires_at,
        )

    def list_reports(self, *, trip_id: str) -> list[ReportRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, generated_by, report_type, format, file_url, email_sent_to, created_at, expires_at
                from public.reports
                where trip_id = %s
                order by created_at desc
                """,
                (trip_id,),
            )
            rows = cur.fetchall()
            result: list[ReportRecord] = []
            for r in rows:
                emails = [x for x in (r[6] or "").split(",") if x]
                result.append(
                    ReportRecord(
                        report_id=str(r[0]),
                        trip_id=str(r[1]),
                        generated_by_member_id=str(r[2]),
                        report_type=str(r[3]),
                        format=str(r[4]),
                        file_url=r[5],
                        emailed_to=emails,
                        created_at=r[7],
                        expires_at=r[8],
                    )
                )
            return result

    def get_report(self, *, report_id: str) -> ReportRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, generated_by, report_type, format, file_url, email_sent_to, created_at, expires_at
                from public.reports
                where id = %s
                limit 1
                """,
                (report_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            emails = [x for x in (row[6] or "").split(",") if x]
            return ReportRecord(
                report_id=str(row[0]),
                trip_id=str(row[1]),
                generated_by_member_id=str(row[2]),
                report_type=str(row[3]),
                format=str(row[4]),
                file_url=row[5],
                emailed_to=emails,
                created_at=row[7],
                expires_at=row[8],
            )

    def append_emailed_to(self, *, report_id: str, recipients: list[str]) -> ReportRecord | None:
        existing = self.get_report(report_id=report_id)
        if existing is None:
            return None
        merged = list(dict.fromkeys([*existing.emailed_to, *recipients]))
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.reports
                set email_sent_to = %s
                where id = %s
                """,
                (",".join(merged), report_id),
            )
            conn.commit()
        existing.emailed_to = merged
        return existing


def build_report_store() -> InMemoryReportStore | PostgresReportStore:
    if settings.use_inmemory_stores:
        return InMemoryReportStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresReportStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory report store: %s", exc)
    return InMemoryReportStore()
