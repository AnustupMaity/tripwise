from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.settings import settings

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


@dataclass
class DisputeRecord:
    dispute_id: str
    trip_id: str
    expense_id: str
    raised_by_profile_id: str
    comment: str
    disputed_amount: float | None
    status: str
    reviewed_by_profile_id: str | None
    reviewed_at: datetime | None
    resolved_by_profile_id: str | None
    resolved_at: datetime | None
    resolution_comment: str | None
    created_at: datetime


@dataclass
class DisputeCommentRecord:
    comment_id: str
    dispute_id: str
    author_profile_id: str
    comment: str
    created_at: datetime


class InMemoryDisputeStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._disputes: dict[str, DisputeRecord] = {}
        self._comments: list[DisputeCommentRecord] = []

    def create_dispute(self, *, trip_id: str, expense_id: str, raised_by_profile_id: str, comment: str, disputed_amount: float | None) -> DisputeRecord:
        with self._lock:
            record = DisputeRecord(
                dispute_id=uuid4().hex,
                trip_id=trip_id,
                expense_id=expense_id,
                raised_by_profile_id=raised_by_profile_id,
                comment=comment,
                disputed_amount=disputed_amount,
                status="open",
                reviewed_by_profile_id=None,
                reviewed_at=None,
                resolved_by_profile_id=None,
                resolved_at=None,
                resolution_comment=None,
                created_at=datetime.now(timezone.utc),
            )
            self._disputes[record.dispute_id] = record
            return record

    def get_dispute(self, *, dispute_id: str) -> DisputeRecord | None:
        with self._lock:
            return self._disputes.get(dispute_id)

    def list_disputes(self, *, trip_id: str) -> list[DisputeRecord]:
        with self._lock:
            return [d for d in self._disputes.values() if d.trip_id == trip_id]

    def set_under_review(self, *, dispute_id: str, reviewer_profile_id: str) -> DisputeRecord:
        with self._lock:
            dispute = self._disputes[dispute_id]
            dispute.status = "in_review"
            dispute.reviewed_by_profile_id = reviewer_profile_id
            dispute.reviewed_at = datetime.now(timezone.utc)
            return dispute

    def resolve_dispute(self, *, dispute_id: str, resolver_profile_id: str, resolution_comment: str) -> DisputeRecord:
        with self._lock:
            dispute = self._disputes[dispute_id]
            dispute.status = "resolved"
            dispute.resolved_by_profile_id = resolver_profile_id
            dispute.resolved_at = datetime.now(timezone.utc)
            dispute.resolution_comment = resolution_comment
            return dispute

    def add_dispute_comment(self, *, dispute_id: str, author_profile_id: str, comment: str) -> DisputeCommentRecord:
        with self._lock:
            row = DisputeCommentRecord(
                comment_id=uuid4().hex,
                dispute_id=dispute_id,
                author_profile_id=author_profile_id,
                comment=comment,
                created_at=datetime.now(timezone.utc),
            )
            self._comments.append(row)
            return row

    def list_dispute_comments(self, *, dispute_id: str) -> list[DisputeCommentRecord]:
        with self._lock:
            return [c for c in self._comments if c.dispute_id == dispute_id]


class PostgresDisputeStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def create_dispute(self, *, trip_id: str, expense_id: str, raised_by_profile_id: str, comment: str, disputed_amount: float | None) -> DisputeRecord:
        dispute_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.disputes (
                    id, trip_id, expense_id, raised_by, comment, disputed_amount,
                    status, created_at, updated_at
                )
                values (
                    %s, %s, %s, %s, %s, %s,
                    'open'::public.dispute_status, %s, %s
                )
                """,
                (dispute_id, trip_id, expense_id, raised_by_profile_id, comment, disputed_amount, created_at, created_at),
            )
            conn.commit()

        return DisputeRecord(
            dispute_id=dispute_id,
            trip_id=trip_id,
            expense_id=expense_id,
            raised_by_profile_id=raised_by_profile_id,
            comment=comment,
            disputed_amount=disputed_amount,
            status="open",
            reviewed_by_profile_id=None,
            reviewed_at=None,
            resolved_by_profile_id=None,
            resolved_at=None,
            resolution_comment=None,
            created_at=created_at,
        )

    def get_dispute(self, *, dispute_id: str) -> DisputeRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, expense_id, raised_by, comment, disputed_amount, status,
                       reviewed_by, reviewed_at, resolved_by, resolved_at, resolution_comment, created_at
                from public.disputes
                where id = %s
                limit 1
                """,
                (dispute_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return DisputeRecord(
                dispute_id=str(row[0]),
                trip_id=str(row[1]),
                expense_id=str(row[2]),
                raised_by_profile_id=str(row[3]),
                comment=row[4],
                disputed_amount=float(row[5]) if row[5] is not None else None,
                status=str(row[6]),
                reviewed_by_profile_id=str(row[7]) if row[7] else None,
                reviewed_at=row[8],
                resolved_by_profile_id=str(row[9]) if row[9] else None,
                resolved_at=row[10],
                resolution_comment=row[11],
                created_at=row[12],
            )

    def list_disputes(self, *, trip_id: str) -> list[DisputeRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, expense_id, raised_by, comment, disputed_amount, status,
                       reviewed_by, reviewed_at, resolved_by, resolved_at, resolution_comment, created_at
                from public.disputes
                where trip_id = %s
                order by created_at desc
                """,
                (trip_id,),
            )
            rows = cur.fetchall()
            result: list[DisputeRecord] = []
            for row in rows:
                result.append(
                    DisputeRecord(
                        dispute_id=str(row[0]),
                        trip_id=str(row[1]),
                        expense_id=str(row[2]),
                        raised_by_profile_id=str(row[3]),
                        comment=row[4],
                        disputed_amount=float(row[5]) if row[5] is not None else None,
                        status=str(row[6]),
                        reviewed_by_profile_id=str(row[7]) if row[7] else None,
                        reviewed_at=row[8],
                        resolved_by_profile_id=str(row[9]) if row[9] else None,
                        resolved_at=row[10],
                        resolution_comment=row[11],
                        created_at=row[12],
                    )
                )
            return result

    def set_under_review(self, *, dispute_id: str, reviewer_profile_id: str) -> DisputeRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.disputes
                set status = 'in_review'::public.dispute_status,
                    reviewed_by = %s,
                    reviewed_at = now(),
                    updated_at = now()
                where id = %s
                """,
                (reviewer_profile_id, dispute_id),
            )
            conn.commit()
        dispute = self.get_dispute(dispute_id=dispute_id)
        if not dispute:
            raise ValueError("dispute not found")
        return dispute

    def resolve_dispute(self, *, dispute_id: str, resolver_profile_id: str, resolution_comment: str) -> DisputeRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.disputes
                set status = 'resolved'::public.dispute_status,
                    resolved_by = %s,
                    resolved_at = now(),
                    resolution_comment = %s,
                    updated_at = now()
                where id = %s
                """,
                (resolver_profile_id, resolution_comment, dispute_id),
            )
            conn.commit()
        dispute = self.get_dispute(dispute_id=dispute_id)
        if not dispute:
            raise ValueError("dispute not found")
        return dispute

    def add_dispute_comment(self, *, dispute_id: str, author_profile_id: str, comment: str) -> DisputeCommentRecord:
        comment_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.dispute_comments (id, dispute_id, author_profile_id, comment, created_at)
                values (%s, %s, %s, %s, %s)
                """,
                (comment_id, dispute_id, author_profile_id, comment, created_at),
            )
            conn.commit()
        return DisputeCommentRecord(
            comment_id=comment_id,
            dispute_id=dispute_id,
            author_profile_id=author_profile_id,
            comment=comment,
            created_at=created_at,
        )

    def list_dispute_comments(self, *, dispute_id: str) -> list[DisputeCommentRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, dispute_id, author_profile_id, comment, created_at
                from public.dispute_comments
                where dispute_id = %s
                order by created_at asc
                """,
                (dispute_id,),
            )
            rows = cur.fetchall()
            return [
                DisputeCommentRecord(
                    comment_id=str(r[0]),
                    dispute_id=str(r[1]),
                    author_profile_id=str(r[2]),
                    comment=r[3],
                    created_at=r[4],
                )
                for r in rows
            ]


def build_dispute_store() -> InMemoryDisputeStore | PostgresDisputeStore:
    if settings.use_inmemory_stores:
        return InMemoryDisputeStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresDisputeStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory dispute store: %s", exc)
    return InMemoryDisputeStore()
