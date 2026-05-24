from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from app.core.settings import settings

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


IdentifierType = Literal["email", "phone"]


@dataclass
class UserRecord:
    user_id: str
    name: str
    nickname: str
    email: str
    phone: str
    upi_id: str | None
    upi_number: str | None
    password_hash: str | None
    google_sub: str | None
    created_at: datetime


@dataclass
class SessionRecord:
    token_hash: str
    user_id: str
    expires_at: datetime
    last_active_at: datetime


@dataclass
class PendingRegistrationRecord:
    email: str
    name: str
    nickname: str
    phone: str
    upi_id: str | None
    upi_number: str | None
    password_hash: str
    created_at: datetime


@dataclass
class OtpChallengeRecord:
    identifier: str
    purpose: str
    otp_hash: str
    expires_at: datetime
    attempts: int
    created_at: datetime


@dataclass
class ResetTokenRecord:
    token_hash: str
    user_id: str
    expires_at: datetime
    created_at: datetime


class InMemoryAuthStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users_by_id: dict[str, UserRecord] = {}
        self._users_by_email: dict[str, str] = {}
        self._users_by_phone: dict[str, str] = {}
        self._users_by_google_sub: dict[str, str] = {}
        self._sessions: dict[str, SessionRecord] = {}
        self._pending_registrations: dict[str, PendingRegistrationRecord] = {}
        self._otp_challenges: dict[tuple[str, str], OtpChallengeRecord] = {}
        self._reset_tokens: dict[str, ResetTokenRecord] = {}
        self._rate_limits: dict[str, tuple[datetime, int]] = {}

    def find_user_by_identifier(self, identifier: str, identifier_type: IdentifierType) -> UserRecord | None:
        with self._lock:
            user_id = self._users_by_email.get(identifier) if identifier_type == "email" else self._users_by_phone.get(identifier)
            if not user_id:
                return None
            return self._users_by_id.get(user_id)

    def find_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self._users_by_id.get(user_id)

    def find_user_by_google_sub(self, google_sub: str) -> UserRecord | None:
        with self._lock:
            user_id = self._users_by_google_sub.get(google_sub)
            if not user_id:
                return None
            return self._users_by_id.get(user_id)

    def create_user(self, *, name: str, nickname: str, email: str, phone: str, upi_id: str | None, upi_number: str | None, password_hash: str | None, google_sub: str | None) -> UserRecord:
        with self._lock:
            user = UserRecord(
                user_id=uuid4().hex,
                name=name,
                nickname=nickname,
                email=email,
                phone=phone,
                upi_id=upi_id,
                upi_number=upi_number,
                password_hash=password_hash,
                google_sub=google_sub,
                created_at=datetime.utcnow(),
            )
            self._users_by_id[user.user_id] = user
            self._users_by_email[email] = user.user_id
            if phone:
                self._users_by_phone[phone] = user.user_id
            if google_sub:
                self._users_by_google_sub[google_sub] = user.user_id
            return user

    def link_google_sub(self, *, user_id: str, google_sub: str) -> None:
        with self._lock:
            user = self._users_by_id[user_id]
            user.google_sub = google_sub
            self._users_by_google_sub[google_sub] = user_id

    def update_password_hash(self, *, user_id: str, password_hash: str) -> None:
        with self._lock:
            user = self._users_by_id[user_id]
            user.password_hash = password_hash

    def complete_profile(self, *, user_id: str, phone: str, upi_id: str | None, upi_number: str | None, nickname: str | None, name: str | None = None) -> UserRecord:
        with self._lock:
            user = self._users_by_id[user_id]
            if name is not None:
                user.name = name
            if phone:
                existing_user_id = self._users_by_phone.get(phone)
                if existing_user_id and existing_user_id != user_id:
                    raise ValueError("phone is already registered")
                if user.phone and user.phone in self._users_by_phone:
                    del self._users_by_phone[user.phone]
                self._users_by_phone[phone] = user_id
                user.phone = phone
            if upi_id is not None:
                user.upi_id = upi_id
            if upi_number is not None:
                user.upi_number = upi_number
            if nickname is not None:
                user.nickname = nickname
            return user

    def update_email(self, *, user_id: str, email: str) -> UserRecord:
        with self._lock:
            user = self._users_by_id[user_id]
            existing_user_id = self._users_by_email.get(email)
            if existing_user_id and existing_user_id != user_id:
                raise ValueError("email is already registered")

            if user.email in self._users_by_email:
                del self._users_by_email[user.email]
            user.email = email
            self._users_by_email[email] = user_id
            return user

    def create_session(self, *, token_hash: str, user_id: str, expires_at: datetime, last_active_at: datetime) -> SessionRecord:
        with self._lock:
            record = SessionRecord(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                last_active_at=last_active_at,
            )
            self._sessions[token_hash] = record
            return record

    def find_session(self, *, token_hash: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(token_hash)

    def touch_session(self, *, token_hash: str, last_active_at: datetime) -> None:
        with self._lock:
            record = self._sessions.get(token_hash)
            if record:
                record.last_active_at = last_active_at

    def delete_session(self, *, token_hash: str) -> None:
        with self._lock:
            self._sessions.pop(token_hash, None)

    def upsert_pending_registration(self, *, email: str, name: str, nickname: str, phone: str, upi_id: str | None, upi_number: str | None, password_hash: str, created_at: datetime) -> None:
        with self._lock:
            self._pending_registrations[email] = PendingRegistrationRecord(
                email=email,
                name=name,
                nickname=nickname,
                phone=phone,
                upi_id=upi_id,
                upi_number=upi_number,
                password_hash=password_hash,
                created_at=created_at,
            )

    def get_pending_registration(self, *, email: str) -> PendingRegistrationRecord | None:
        with self._lock:
            return self._pending_registrations.get(email)

    def delete_pending_registration(self, *, email: str) -> None:
        with self._lock:
            self._pending_registrations.pop(email, None)

    def create_otp_challenge(self, *, identifier: str, purpose: str, otp_hash: str, expires_at: datetime, created_at: datetime) -> None:
        with self._lock:
            self._otp_challenges[(identifier, purpose)] = OtpChallengeRecord(
                identifier=identifier,
                purpose=purpose,
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempts=0,
                created_at=created_at,
            )

    def get_otp_challenge(self, *, identifier: str, purpose: str) -> OtpChallengeRecord | None:
        with self._lock:
            return self._otp_challenges.get((identifier, purpose))

    def increment_otp_attempts(self, *, identifier: str, purpose: str) -> int:
        with self._lock:
            key = (identifier, purpose)
            record = self._otp_challenges.get(key)
            if record is None:
                return 0
            record.attempts += 1
            return record.attempts

    def delete_otp_challenge(self, *, identifier: str, purpose: str) -> None:
        with self._lock:
            self._otp_challenges.pop((identifier, purpose), None)

    def rename_otp_challenge(self, *, old_identifier: str, new_identifier: str, purpose: str) -> None:
        with self._lock:
            record = self._otp_challenges.pop((old_identifier, purpose), None)
            if record is None:
                return
            record.identifier = new_identifier
            self._otp_challenges[(new_identifier, purpose)] = record

    def create_reset_token(self, *, token_hash: str, user_id: str, expires_at: datetime, created_at: datetime) -> None:
        with self._lock:
            self._reset_tokens[token_hash] = ResetTokenRecord(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                created_at=created_at,
            )

    def get_reset_token(self, *, token_hash: str) -> ResetTokenRecord | None:
        with self._lock:
            return self._reset_tokens.get(token_hash)

    def delete_reset_token(self, *, token_hash: str) -> None:
        with self._lock:
            self._reset_tokens.pop(token_hash, None)

    def consume_rate_limit(self, *, scope_key: str, limit_count: int, window_seconds: int, now: datetime) -> bool:
        with self._lock:
            started_at, count = self._rate_limits.get(scope_key, (now, 0))
            if started_at + timedelta(seconds=window_seconds) < now:
                started_at, count = now, 0
            if count >= limit_count:
                self._rate_limits[scope_key] = (started_at, count)
                return False
            self._rate_limits[scope_key] = (started_at, count + 1)
            return True


class PostgresAuthStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def find_user_by_identifier(self, identifier: str, identifier_type: IdentifierType) -> UserRecord | None:
        column = "email" if identifier_type == "email" else "phone"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select id, name, coalesce(nickname, ''), email, coalesce(phone, ''), upi_id, upi_number, password_hash, google_sub, created_at
                from public.profiles
                where {column} = %s
                limit 1
                """,
                (identifier,),
            )
            row = cur.fetchone()
            return _user_from_row(row) if row else None

    def find_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, name, coalesce(nickname, ''), email, coalesce(phone, ''), upi_id, upi_number, password_hash, google_sub, created_at
                from public.profiles
                where id = %s
                limit 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return _user_from_row(row) if row else None

    def find_user_by_google_sub(self, google_sub: str) -> UserRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, name, coalesce(nickname, ''), email, coalesce(phone, ''), upi_id, upi_number, password_hash, google_sub, created_at
                from public.profiles
                where google_sub = %s
                limit 1
                """,
                (google_sub,),
            )
            row = cur.fetchone()
            return _user_from_row(row) if row else None

    def create_user(self, *, name: str, nickname: str, email: str, phone: str, upi_id: str | None, upi_number: str | None, password_hash: str | None, google_sub: str | None) -> UserRecord:
        user_id = str(uuid4())
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.profiles (id, name, nickname, email, phone, upi_id, upi_number, password_hash, google_sub)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, name, nickname, email, phone or None, upi_id, upi_number, password_hash, google_sub),
            )
            conn.commit()
        created = self.find_user_by_id(user_id)
        if not created:
            raise ValueError("failed to create user")
        return created

    def link_google_sub(self, *, user_id: str, google_sub: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("update public.profiles set google_sub = %s where id = %s", (google_sub, user_id))
            conn.commit()

    def update_password_hash(self, *, user_id: str, password_hash: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("update public.profiles set password_hash = %s where id = %s", (password_hash, user_id))
            conn.commit()

    def complete_profile(self, *, user_id: str, phone: str, upi_id: str | None, upi_number: str | None, nickname: str | None, name: str | None = None) -> UserRecord:
        with self._conn() as conn, conn.cursor() as cur:
            if phone:
                cur.execute("select id from public.profiles where phone = %s and id <> %s limit 1", (phone, user_id))
                if cur.fetchone():
                    raise ValueError("phone is already registered")

            cur.execute(
                """
                update public.profiles
                set
                    name = coalesce(%s, name),
                    phone = case when %s = '' then phone else %s end,
                    upi_id = %s,
                    upi_number = %s,
                    nickname = coalesce(%s, nickname)
                where id = %s
                """,
                (name, phone, phone, upi_id, upi_number, nickname, user_id),
            )
            conn.commit()

        updated = self.find_user_by_id(user_id)
        if not updated:
            raise ValueError("user not found")
        return updated

    def update_email(self, *, user_id: str, email: str) -> UserRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("select id from public.profiles where email = %s and id <> %s limit 1", (email, user_id))
            if cur.fetchone():
                raise ValueError("email is already registered")

            cur.execute("update public.profiles set email = %s where id = %s", (email, user_id))
            conn.commit()

        updated = self.find_user_by_id(user_id)
        if not updated:
            raise ValueError("user not found")
        return updated

    def create_session(self, *, token_hash: str, user_id: str, expires_at: datetime, last_active_at: datetime) -> SessionRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.auth_sessions (token_hash, user_id, expires_at, last_active_at)
                values (%s, %s, %s, %s)
                """,
                (token_hash, user_id, expires_at, last_active_at),
            )
            conn.commit()
        return SessionRecord(token_hash=token_hash, user_id=user_id, expires_at=expires_at, last_active_at=last_active_at)

    def find_session(self, *, token_hash: str) -> SessionRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select token_hash, user_id, expires_at, last_active_at
                from public.auth_sessions
                where token_hash = %s
                limit 1
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SessionRecord(token_hash=row[0], user_id=str(row[1]), expires_at=row[2], last_active_at=row[3])

    def touch_session(self, *, token_hash: str, last_active_at: datetime) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "update public.auth_sessions set last_active_at = %s where token_hash = %s",
                (last_active_at, token_hash),
            )
            conn.commit()

    def delete_session(self, *, token_hash: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("delete from public.auth_sessions where token_hash = %s", (token_hash,))
            conn.commit()

    def upsert_pending_registration(self, *, email: str, name: str, nickname: str, phone: str, upi_id: str | None, upi_number: str | None, password_hash: str, created_at: datetime) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.auth_pending_registrations (email, name, nickname, phone, upi_id, upi_number, password_hash, created_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (email)
                do update set
                    name = excluded.name,
                    nickname = excluded.nickname,
                    phone = excluded.phone,
                    upi_id = excluded.upi_id,
                    upi_number = excluded.upi_number,
                    password_hash = excluded.password_hash,
                    created_at = excluded.created_at
                """,
                (email, name, nickname, phone, upi_id, upi_number, password_hash, created_at),
            )
            conn.commit()

    def get_pending_registration(self, *, email: str) -> PendingRegistrationRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select email, name, nickname, phone, upi_id, upi_number, password_hash, created_at
                from public.auth_pending_registrations
                where email = %s
                limit 1
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return PendingRegistrationRecord(
                email=row[0],
                name=row[1],
                nickname=row[2],
                phone=row[3],
                upi_id=row[4],
                upi_number=row[5],
                password_hash=row[6],
                created_at=row[7],
            )

    def delete_pending_registration(self, *, email: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("delete from public.auth_pending_registrations where email = %s", (email,))
            conn.commit()

    def create_otp_challenge(self, *, identifier: str, purpose: str, otp_hash: str, expires_at: datetime, created_at: datetime) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.auth_otp_challenges (identifier, purpose, otp_hash, expires_at, attempts, created_at)
                values (%s, %s, %s, %s, 0, %s)
                on conflict (identifier, purpose)
                do update set
                    otp_hash = excluded.otp_hash,
                    expires_at = excluded.expires_at,
                    attempts = 0,
                    created_at = excluded.created_at
                """,
                (identifier, purpose, otp_hash, expires_at, created_at),
            )
            conn.commit()

    def get_otp_challenge(self, *, identifier: str, purpose: str) -> OtpChallengeRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select identifier, purpose, otp_hash, expires_at, attempts, created_at
                from public.auth_otp_challenges
                where identifier = %s and purpose = %s
                limit 1
                """,
                (identifier, purpose),
            )
            row = cur.fetchone()
            if not row:
                return None
            return OtpChallengeRecord(
                identifier=row[0],
                purpose=row[1],
                otp_hash=row[2],
                expires_at=row[3],
                attempts=row[4],
                created_at=row[5],
            )

    def increment_otp_attempts(self, *, identifier: str, purpose: str) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.auth_otp_challenges
                set attempts = attempts + 1
                where identifier = %s and purpose = %s
                returning attempts
                """,
                (identifier, purpose),
            )
            row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else 0

    def delete_otp_challenge(self, *, identifier: str, purpose: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "delete from public.auth_otp_challenges where identifier = %s and purpose = %s",
                (identifier, purpose),
            )
            conn.commit()

    def rename_otp_challenge(self, *, old_identifier: str, new_identifier: str, purpose: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "update public.auth_otp_challenges set identifier = %s where identifier = %s and purpose = %s",
                (new_identifier, old_identifier, purpose),
            )
            conn.commit()

    def create_reset_token(self, *, token_hash: str, user_id: str, expires_at: datetime, created_at: datetime) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.auth_password_reset_tokens (token_hash, user_id, expires_at, created_at)
                values (%s, %s, %s, %s)
                on conflict (token_hash) do update set
                    user_id = excluded.user_id,
                    expires_at = excluded.expires_at,
                    created_at = excluded.created_at
                """,
                (token_hash, user_id, expires_at, created_at),
            )
            conn.commit()

    def get_reset_token(self, *, token_hash: str) -> ResetTokenRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select token_hash, user_id, expires_at, created_at
                from public.auth_password_reset_tokens
                where token_hash = %s
                limit 1
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ResetTokenRecord(
                token_hash=row[0],
                user_id=str(row[1]),
                expires_at=row[2],
                created_at=row[3],
            )

    def delete_reset_token(self, *, token_hash: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("delete from public.auth_password_reset_tokens where token_hash = %s", (token_hash,))
            conn.commit()

    def consume_rate_limit(self, *, scope_key: str, limit_count: int, window_seconds: int, now: datetime) -> bool:
        window_started = now
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select scope_key, window_started_at, count
                from public.auth_rate_limits
                where scope_key = %s
                for update
                """,
                (scope_key,),
            )
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    """
                    insert into public.auth_rate_limits (scope_key, window_started_at, count, updated_at)
                    values (%s, %s, 1, %s)
                    """,
                    (scope_key, window_started, now),
                )
                conn.commit()
                return True

            _, started_at, count = row
            if started_at + timedelta(seconds=window_seconds) < now:
                cur.execute(
                    """
                    update public.auth_rate_limits
                    set window_started_at = %s, count = 1, updated_at = %s
                    where scope_key = %s
                    """,
                    (window_started, now, scope_key),
                )
                conn.commit()
                return True

            if count >= limit_count:
                cur.execute(
                    "update public.auth_rate_limits set updated_at = %s where scope_key = %s",
                    (now, scope_key),
                )
                conn.commit()
                return False

            cur.execute(
                """
                update public.auth_rate_limits
                set count = count + 1, updated_at = %s
                where scope_key = %s
                """,
                (now, scope_key),
            )
            conn.commit()
            return True


def _user_from_row(row: tuple) -> UserRecord:
    return UserRecord(
        user_id=str(row[0]),
        name=row[1],
        nickname=row[2],
        email=row[3],
        phone=row[4],
        upi_id=row[5],
        upi_number=row[6],
        password_hash=row[7],
        google_sub=row[8],
        created_at=row[9],
    )


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_auth_store() -> InMemoryAuthStore | PostgresAuthStore:
    if settings.use_inmemory_stores:
        return InMemoryAuthStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresAuthStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory auth store: %s", exc)
    return InMemoryAuthStore()
