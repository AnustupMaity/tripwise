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
class ExpenseRecord:
    expense_id: str
    trip_id: str
    amount: float
    description: str
    split_type: str
    status: str
    created_by_profile_id: str
    approved_by_profile_id: str | None
    approved_at: datetime | None
    created_at: datetime


@dataclass
class ExpensePayerRecord:
    expense_id: str
    member_id: str
    amount_paid: float


@dataclass
class ExpenseSplitRecord:
    expense_id: str
    member_id: str
    amount_owed: float | None
    percentage: float | None
    excluded: bool


class InMemoryExpenseStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._expenses: dict[str, ExpenseRecord] = {}
        self._expense_payers: list[ExpensePayerRecord] = []
        self._expense_splits: list[ExpenseSplitRecord] = []

    def create_expense(self, *, trip_id: str, amount: float, description: str, split_type: str, status: str, created_by_profile_id: str, approved_by_profile_id: str | None, approved_at: datetime | None) -> ExpenseRecord:
        with self._lock:
            record = ExpenseRecord(
                expense_id=uuid4().hex,
                trip_id=trip_id,
                amount=amount,
                description=description,
                split_type=split_type,
                status=status,
                created_by_profile_id=created_by_profile_id,
                approved_by_profile_id=approved_by_profile_id,
                approved_at=approved_at,
                created_at=datetime.now(timezone.utc),
            )
            self._expenses[record.expense_id] = record
            return record

    def insert_payers(self, *, expense_id: str, payers: list[tuple[str, float]]) -> None:
        with self._lock:
            for member_id, amount_paid in payers:
                self._expense_payers.append(
                    ExpensePayerRecord(
                        expense_id=expense_id,
                        member_id=member_id,
                        amount_paid=amount_paid,
                    )
                )

    def insert_splits(self, *, expense_id: str, splits: list[tuple[str, float | None, float | None, bool]]) -> None:
        with self._lock:
            for member_id, amount_owed, percentage, excluded in splits:
                self._expense_splits.append(
                    ExpenseSplitRecord(
                        expense_id=expense_id,
                        member_id=member_id,
                        amount_owed=amount_owed,
                        percentage=percentage,
                        excluded=excluded,
                    )
                )

    def get_expense(self, *, expense_id: str) -> ExpenseRecord | None:
        with self._lock:
            return self._expenses.get(expense_id)

    def list_expenses(self, *, trip_id: str) -> list[ExpenseRecord]:
        with self._lock:
            return [e for e in self._expenses.values() if e.trip_id == trip_id]

    def set_expense_status(self, *, expense_id: str, status: str, approved_by_profile_id: str | None, approved_at: datetime | None) -> ExpenseRecord:
        with self._lock:
            record = self._expenses[expense_id]
            record.status = status
            record.approved_by_profile_id = approved_by_profile_id
            record.approved_at = approved_at
            return record

    def list_expense_payers(self, *, expense_id: str) -> list[ExpensePayerRecord]:
        with self._lock:
            return [p for p in self._expense_payers if p.expense_id == expense_id]

    def list_expense_splits(self, *, expense_id: str) -> list[ExpenseSplitRecord]:
        with self._lock:
            return [s for s in self._expense_splits if s.expense_id == expense_id]


class PostgresExpenseStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def create_expense(self, *, trip_id: str, amount: float, description: str, split_type: str, status: str, created_by_profile_id: str, approved_by_profile_id: str | None, approved_at: datetime | None) -> ExpenseRecord:
        expense_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.expenses (id, trip_id, amount, description, created_by, split_type, status, approved_by, approved_at, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s::public.split_type, %s::public.expense_status, %s, %s, %s, %s)
                """,
                (
                    expense_id,
                    trip_id,
                    amount,
                    description,
                    created_by_profile_id,
                    split_type,
                    status,
                    approved_by_profile_id,
                    approved_at,
                    created_at,
                    created_at,
                ),
            )
            conn.commit()

        return ExpenseRecord(
            expense_id=expense_id,
            trip_id=trip_id,
            amount=amount,
            description=description,
            split_type=split_type,
            status=status,
            created_by_profile_id=created_by_profile_id,
            approved_by_profile_id=approved_by_profile_id,
            approved_at=approved_at,
            created_at=created_at,
        )

    def insert_payers(self, *, expense_id: str, payers: list[tuple[str, float]]) -> None:
        if not payers:
            return
        with self._conn() as conn, conn.cursor() as cur:
            for member_id, amount_paid in payers:
                cur.execute(
                    """
                    insert into public.expense_payers (id, expense_id, member_id, amount_paid)
                    values (%s, %s, %s, %s)
                    """,
                    (str(uuid4()), expense_id, member_id, amount_paid),
                )
            conn.commit()

    def insert_splits(self, *, expense_id: str, splits: list[tuple[str, float | None, float | None, bool]]) -> None:
        if not splits:
            return
        with self._conn() as conn, conn.cursor() as cur:
            for member_id, amount_owed, percentage, excluded in splits:
                cur.execute(
                    """
                    insert into public.expense_splits (id, expense_id, member_id, amount_owed, percentage, excluded)
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid4()), expense_id, member_id, amount_owed, percentage, excluded),
                )
            conn.commit()

    def get_expense(self, *, expense_id: str) -> ExpenseRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, amount, description, split_type, status, created_by, approved_by, approved_at, created_at
                from public.expenses
                where id = %s
                limit 1
                """,
                (expense_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ExpenseRecord(
                expense_id=str(row[0]),
                trip_id=str(row[1]),
                amount=float(row[2]),
                description=row[3],
                split_type=str(row[4]),
                status=str(row[5]),
                created_by_profile_id=str(row[6]),
                approved_by_profile_id=str(row[7]) if row[7] else None,
                approved_at=row[8],
                created_at=row[9],
            )

    def list_expenses(self, *, trip_id: str) -> list[ExpenseRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, amount, description, split_type, status, created_by, approved_by, approved_at, created_at
                from public.expenses
                where trip_id = %s
                order by created_at desc
                """,
                (trip_id,),
            )
            rows = cur.fetchall()
            return [
                ExpenseRecord(
                    expense_id=str(r[0]),
                    trip_id=str(r[1]),
                    amount=float(r[2]),
                    description=r[3],
                    split_type=str(r[4]),
                    status=str(r[5]),
                    created_by_profile_id=str(r[6]),
                    approved_by_profile_id=str(r[7]) if r[7] else None,
                    approved_at=r[8],
                    created_at=r[9],
                )
                for r in rows
            ]

    def set_expense_status(self, *, expense_id: str, status: str, approved_by_profile_id: str | None, approved_at: datetime | None) -> ExpenseRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.expenses
                set status = %s::public.expense_status,
                    approved_by = %s,
                    approved_at = %s,
                    updated_at = now()
                where id = %s
                """,
                (status, approved_by_profile_id, approved_at, expense_id),
            )
            conn.commit()
        record = self.get_expense(expense_id=expense_id)
        if not record:
            raise ValueError("expense not found")
        return record

    def list_expense_payers(self, *, expense_id: str) -> list[ExpensePayerRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select expense_id, member_id, amount_paid
                from public.expense_payers
                where expense_id = %s
                """,
                (expense_id,),
            )
            rows = cur.fetchall()
            return [
                ExpensePayerRecord(
                    expense_id=str(r[0]),
                    member_id=str(r[1]),
                    amount_paid=float(r[2]),
                )
                for r in rows
            ]

    def list_expense_splits(self, *, expense_id: str) -> list[ExpenseSplitRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select expense_id, member_id, amount_owed, percentage, excluded
                from public.expense_splits
                where expense_id = %s
                """,
                (expense_id,),
            )
            rows = cur.fetchall()
            return [
                ExpenseSplitRecord(
                    expense_id=str(r[0]),
                    member_id=str(r[1]),
                    amount_owed=float(r[2]) if r[2] is not None else None,
                    percentage=float(r[3]) if r[3] is not None else None,
                    excluded=bool(r[4]),
                )
                for r in rows
            ]


def build_expense_store() -> InMemoryExpenseStore | PostgresExpenseStore:
    if settings.use_inmemory_stores:
        return InMemoryExpenseStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresExpenseStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory expense store: %s", exc)
    return InMemoryExpenseStore()
