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
class PaymentRecord:
    payment_id: str
    trip_id: str
    from_member_id: str
    to_member_id: str
    amount: float
    method: str
    status: str
    paid_at: datetime | None
    created_at: datetime


class InMemoryPaymentStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payments: dict[str, PaymentRecord] = {}

    def create_payment(self, *, trip_id: str, from_member_id: str, to_member_id: str, amount: float, method: str, status: str, paid_at: datetime | None) -> PaymentRecord:
        with self._lock:
            record = PaymentRecord(
                payment_id=uuid4().hex,
                trip_id=trip_id,
                from_member_id=from_member_id,
                to_member_id=to_member_id,
                amount=amount,
                method=method,
                status=status,
                paid_at=paid_at,
                created_at=datetime.now(timezone.utc),
            )
            self._payments[record.payment_id] = record
            return record

    def list_payments(self, *, trip_id: str) -> list[PaymentRecord]:
        with self._lock:
            return [p for p in self._payments.values() if p.trip_id == trip_id]


class PostgresPaymentStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def create_payment(self, *, trip_id: str, from_member_id: str, to_member_id: str, amount: float, method: str, status: str, paid_at: datetime | None) -> PaymentRecord:
        payment_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.payments (id, trip_id, from_member_id, to_member_id, amount, method, status, paid_at, created_at)
                values (%s, %s, %s, %s, %s, %s::public.payment_method, %s::public.payment_status, %s, %s)
                """,
                (payment_id, trip_id, from_member_id, to_member_id, amount, method, status, paid_at, created_at),
            )
            conn.commit()

        return PaymentRecord(
            payment_id=payment_id,
            trip_id=trip_id,
            from_member_id=from_member_id,
            to_member_id=to_member_id,
            amount=amount,
            method=method,
            status=status,
            paid_at=paid_at,
            created_at=created_at,
        )

    def list_payments(self, *, trip_id: str) -> list[PaymentRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, from_member_id, to_member_id, amount, method, status, paid_at, created_at
                from public.payments
                where trip_id = %s
                order by created_at desc
                """,
                (trip_id,),
            )
            rows = cur.fetchall()
            return [
                PaymentRecord(
                    payment_id=str(r[0]),
                    trip_id=str(r[1]),
                    from_member_id=str(r[2]),
                    to_member_id=str(r[3]),
                    amount=float(r[4]),
                    method=str(r[5]),
                    status=str(r[6]),
                    paid_at=r[7],
                    created_at=r[8],
                )
                for r in rows
            ]


def build_payment_store() -> InMemoryPaymentStore | PostgresPaymentStore:
    if settings.use_inmemory_stores:
        return InMemoryPaymentStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresPaymentStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory payment store: %s", exc)
    return InMemoryPaymentStore()
