from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.settings import settings
from app.core.security import generate_otp, generate_token, hash_password, verify_password
from app.services.auth_store import build_auth_store, hash_session_token
from app.services.notification_service import notification_service
from app.services.trip_store import build_trip_store

OTP_TTL_MINUTES = 10
SESSION_VALID_DAYS = 30
INACTIVITY_TIMEOUT_DAYS = 30
RESET_TOKEN_TTL_MINUTES = 15
MAX_OTP_ATTEMPTS = 5
OTP_SEND_LIMIT = 3
OTP_SEND_WINDOW_SECONDS = 30 * 60

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")
PASSWORD_POLICY_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")


@dataclass
class SessionRecord:
    token: str
    user_id: str
    expires_at: datetime
    last_active_at: datetime


class AuthService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store = build_auth_store()
        self._trip_store = build_trip_store()

    def request_registration_otp(self, *, name: str, nickname: str, email: str, phone: str, password: str, upi_id: str | None, upi_number: str | None) -> dict[str, str]:
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        validate_password_strength(password)
        now = utc_now()

        with self._lock:
            self._consume_otp_rate_limit(scope=f"register:{normalized_email}", now=now)
            if self._store.find_user_by_identifier(normalized_email, "email"):
                raise ValueError("email is already registered")
            if self._store.find_user_by_identifier(normalized_phone, "phone"):
                raise ValueError("phone is already registered")

            password_hash = hash_password(password)
            self._store.upsert_pending_registration(
                email=normalized_email,
                name=name,
                nickname=nickname,
                phone=normalized_phone,
                upi_id=upi_id,
                upi_number=upi_number,
                password_hash=password_hash,
                created_at=now,
            )
            otp_value, expires_at = self._issue_otp(identifier=normalized_email, purpose="register", now=now)
            notification_service.enqueue_otp(
                identifier=normalized_email,
                purpose="registration",
                otp=otp_value,
                expires_minutes=OTP_TTL_MINUTES,
            )

        return build_otp_response(otp_value=otp_value, expires_at=expires_at)

    def verify_registration_otp(self, *, email: str, otp: str) -> dict[str, str]:
        normalized_email = normalize_email(email)

        with self._lock:
            self._verify_otp_or_raise(identifier=normalized_email, purpose="register", otp=otp)

            pending = self._store.get_pending_registration(email=normalized_email)
            if pending is None:
                raise ValueError("no pending registration found")

            user = self._store.create_user(
                name=pending.name,
                nickname=pending.nickname,
                email=pending.email,
                phone=pending.phone,
                upi_id=pending.upi_id,
                upi_number=pending.upi_number,
                password_hash=pending.password_hash,
                google_sub=None,
            )

            self._store.delete_pending_registration(email=normalized_email)
            self._store.delete_otp_challenge(identifier=normalized_email, purpose="register")
            self._link_pending_trip_memberships(email=normalized_email, user_id=user.user_id)

            session = self._create_session(user.user_id)
            return {
                "userId": user.user_id,
                "sessionToken": session.token,
                "sessionExpiresAt": session.expires_at.isoformat(),
            }

    def request_login_otp(self, *, identifier: str) -> dict[str, str]:
        normalized_identifier, identifier_type = normalize_identifier(identifier)
        now = utc_now()

        with self._lock:
            self._consume_otp_rate_limit(scope=f"login:{normalized_identifier}", now=now)
            if not self._store.find_user_by_identifier(normalized_identifier, identifier_type):
                raise ValueError("account not registered. please sign up")

            otp_value, expires_at = self._issue_otp(identifier=normalized_identifier, purpose="login", now=now)
            notification_service.enqueue_otp(
                identifier=normalized_identifier,
                purpose="login",
                otp=otp_value,
                expires_minutes=OTP_TTL_MINUTES,
            )

        return build_otp_response(otp_value=otp_value, expires_at=expires_at)

    def verify_login_otp(self, *, identifier: str, otp: str) -> dict[str, str]:
        normalized_identifier, identifier_type = normalize_identifier(identifier)

        with self._lock:
            self._verify_otp_or_raise(identifier=normalized_identifier, purpose="login", otp=otp)

            user = self._store.find_user_by_identifier(normalized_identifier, identifier_type)
            if not user:
                raise ValueError("account not found")

            self._store.delete_otp_challenge(identifier=normalized_identifier, purpose="login")
            self._link_pending_trip_memberships(email=user.email, user_id=user.user_id)
            session = self._create_session(user.user_id)
            return {
                "userId": user.user_id,
                "sessionToken": session.token,
                "sessionExpiresAt": session.expires_at.isoformat(),
            }

    def login_with_password(self, *, identifier: str, password: str) -> dict[str, str]:
        normalized_identifier, identifier_type = normalize_identifier(identifier)

        with self._lock:
            user = self._store.find_user_by_identifier(normalized_identifier, identifier_type)
            if not user:
                raise ValueError("invalid credentials")

            if not user.password_hash or not verify_password(password, user.password_hash):
                raise ValueError("invalid credentials")

            self._link_pending_trip_memberships(email=user.email, user_id=user.user_id)
            session = self._create_session(user.user_id)
            return {
                "userId": user.user_id,
                "sessionToken": session.token,
                "sessionExpiresAt": session.expires_at.isoformat(),
            }

    def request_forgot_password_otp(self, *, identifier: str) -> dict[str, str]:
        normalized_identifier, identifier_type = normalize_identifier(identifier)
        now = utc_now()

        with self._lock:
            self._consume_otp_rate_limit(scope=f"reset:{normalized_identifier}", now=now)
            user = self._store.find_user_by_identifier(normalized_identifier, identifier_type)
            if not user:
                return {"message": "If account exists, OTP has been sent."}

            otp_value, expires_at = self._issue_otp(identifier=normalized_identifier, purpose="reset", now=now)
            notification_service.enqueue_otp(
                identifier=normalized_identifier,
                purpose="password reset",
                otp=otp_value,
                expires_minutes=OTP_TTL_MINUTES,
            )

        return build_otp_response(otp_value=otp_value, expires_at=expires_at)

    def verify_forgot_password_otp(self, *, identifier: str, otp: str) -> dict[str, str]:
        normalized_identifier, identifier_type = normalize_identifier(identifier)

        with self._lock:
            self._verify_otp_or_raise(identifier=normalized_identifier, purpose="reset", otp=otp)

            user = self._store.find_user_by_identifier(normalized_identifier, identifier_type)
            if not user:
                raise ValueError("account not found")

            reset_token = generate_token(24)
            token_hash = hash_session_token(reset_token)
            self._store.create_reset_token(
                token_hash=token_hash,
                user_id=user.user_id,
                expires_at=utc_now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
                created_at=utc_now(),
            )
            self._store.delete_otp_challenge(identifier=normalized_identifier, purpose="reset")

            return {
                "resetToken": reset_token,
                "expiresAt": (utc_now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)).isoformat(),
            }

    def reset_password(self, *, reset_token: str, new_password: str) -> dict[str, str]:
        validate_password_strength(new_password)
        with self._lock:
            token_hash = hash_session_token(reset_token)
            reset_record = self._store.get_reset_token(token_hash=token_hash)
            if reset_record is None:
                raise ValueError("invalid reset token")
            if reset_record.expires_at < utc_now():
                self._store.delete_reset_token(token_hash=token_hash)
                raise ValueError("reset token expired")

            self._store.update_password_hash(
                user_id=reset_record.user_id,
                password_hash=hash_password(new_password),
            )
            user = self._store.find_user_by_id(reset_record.user_id)
            self._store.delete_reset_token(token_hash=token_hash)

            timestamp = utc_now().isoformat()
            if user and user.email:
                notification_service.enqueue_email(
                    recipient=user.email,
                    subject="TripWise password changed",
                    html_content=f"<p>Your TripWise password was changed at {timestamp}.</p>",
                    metadata={"eventType": "password_changed", "userId": user.user_id},
                )
            return {
                "message": "Password reset successful.",
                "confirmationEmailSentAt": timestamp,
            }

    def login_with_google(self, *, id_token: str) -> dict[str, str | bool]:
        if not settings.google_client_id:
            raise ValueError("GOOGLE_CLIENT_ID is not configured")

        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token
        except Exception as exc:  # pragma: no cover
            raise ValueError("google-auth is not installed") from exc

        try:
            token_info = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                settings.google_client_id,
            )
        except Exception as exc:  # pragma: no cover
            raise ValueError("invalid google token") from exc

        google_sub = str(token_info.get("sub") or "").strip()
        if not google_sub:
            raise ValueError("google token missing subject")
        email_value = str(token_info.get("email") or "").strip()
        name_value = str(token_info.get("name") or "").strip()
        email = normalize_email(email_value) if email_value else None
        name = name_value or None

        with self._lock:
            user = self._store.find_user_by_google_sub(google_sub)

            if user is None and email:
                normalized_email = normalize_email(email)
                user = self._store.find_user_by_identifier(normalized_email, "email")

            if user is None:
                new_id = generate_token(16)
                normalized_email = normalize_email(email) if email else f"google-{new_id}@pending.local"
                user = self._store.create_user(
                    name=name or "",
                    nickname="",
                    email=normalized_email,
                    phone="",
                    upi_id=None,
                    upi_number=None,
                    password_hash=None,
                    google_sub=google_sub,
                )
            else:
                self._store.link_google_sub(user_id=user.user_id, google_sub=google_sub)

            self._link_pending_trip_memberships(email=user.email, user_id=user.user_id)
            session = self._create_session(user.user_id)
            requires_profile_completion = not bool(user.phone) or not bool(user.upi_id or user.upi_number)

            return {
                "userId": user.user_id,
                "sessionToken": session.token,
                "sessionExpiresAt": session.expires_at.isoformat(),
                "requiresProfileCompletion": requires_profile_completion,
            }

    def validate_session(self, *, token: str) -> dict[str, str | bool]:
        with self._lock:
            token_hash = hash_session_token(token)
            session = self._store.find_session(token_hash=token_hash)
            if session is None:
                raise ValueError("invalid session")

            now = utc_now()
            if session.expires_at < now:
                self._store.delete_session(token_hash=token_hash)
                raise ValueError("session expired")

            if session.last_active_at + timedelta(days=INACTIVITY_TIMEOUT_DAYS) < now:
                self._store.delete_session(token_hash=token_hash)
                raise ValueError("session expired due to inactivity")

            user = self._store.find_user_by_id(session.user_id)
            if user is None:
                self._store.delete_session(token_hash=token_hash)
                raise ValueError("user not found for session")

            self._store.touch_session(token_hash=token_hash, last_active_at=now)
            return {
                "valid": True,
                "userId": session.user_id,
                "name": user.name,
                "nickname": user.nickname,
                "email": user.email,
                "phone": user.phone,
                "expiresAt": session.expires_at.isoformat(),
                "lastActiveAt": now.isoformat(),
            }

    def complete_profile(self, *, session_token: str, phone: str, upi_id: str | None, upi_number: str | None, nickname: str | None) -> dict[str, str | bool]:
        normalized_phone = normalize_phone(phone)

        with self._lock:
            token_hash = hash_session_token(session_token)
            session = self._store.find_session(token_hash=token_hash)
            if session is None:
                raise ValueError("invalid session")

            updated_user = self._store.complete_profile(
                user_id=session.user_id,
                phone=normalized_phone,
                upi_id=upi_id,
                upi_number=upi_number,
                nickname=nickname,
            )

            requires_profile_completion = not bool(updated_user.phone) or not bool(updated_user.upi_id or updated_user.upi_number)
            return {
                "userId": updated_user.user_id,
                "requiresProfileCompletion": requires_profile_completion,
                "phone": updated_user.phone,
                "nickname": updated_user.nickname,
            }

    def is_registered_identifier(self, *, identifier: str) -> bool:
        normalized_identifier, identifier_type = normalize_identifier(identifier)
        with self._lock:
            return bool(self._store.find_user_by_identifier(normalized_identifier, identifier_type))

    def _create_session(self, user_id: str) -> SessionRecord:
        now = utc_now()
        token = generate_token(32)
        token_hash = hash_session_token(token)
        session = SessionRecord(
            token=token,
            user_id=user_id,
            expires_at=now + timedelta(days=SESSION_VALID_DAYS),
            last_active_at=now,
        )
        self._store.create_session(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=session.expires_at,
            last_active_at=session.last_active_at,
        )
        return session

    def _link_pending_trip_memberships(self, *, email: str, user_id: str) -> None:
        user = self._store.find_user_by_id(user_id)
        if user is None:
            return
        profile = self._trip_store.ensure_profile_for_identifier(
            identifier=normalize_email(email),
            display_name=user.name or user.nickname or None,
        )
        self._trip_store.link_guest_memberships_to_profile(
            identifier=normalize_email(email),
            profile_id=profile.profile_id,
        )

    def _issue_otp(self, *, identifier: str, purpose: str, now: datetime) -> tuple[str, datetime]:
        otp_value = generate_otp()
        expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)
        self._store.create_otp_challenge(
            identifier=identifier,
            purpose=purpose,
            otp_hash=hash_session_token(otp_value),
            expires_at=expires_at,
            created_at=now,
        )
        return otp_value, expires_at

    def _verify_otp_or_raise(self, *, identifier: str, purpose: str, otp: str) -> None:
        challenge = self._store.get_otp_challenge(identifier=identifier, purpose=purpose)
        if challenge is None:
            raise ValueError(f"no {purpose} OTP found")

        now = utc_now()
        if challenge.expires_at < now:
            self._store.delete_otp_challenge(identifier=identifier, purpose=purpose)
            raise ValueError("OTP expired")

        if challenge.attempts >= MAX_OTP_ATTEMPTS:
            self._store.delete_otp_challenge(identifier=identifier, purpose=purpose)
            raise ValueError("OTP attempt limit exceeded")

        if challenge.otp_hash != hash_session_token(otp):
            attempts = self._store.increment_otp_attempts(identifier=identifier, purpose=purpose)
            if attempts >= MAX_OTP_ATTEMPTS:
                self._store.delete_otp_challenge(identifier=identifier, purpose=purpose)
                raise ValueError("OTP attempt limit exceeded")
            raise ValueError("invalid OTP")

    def _consume_otp_rate_limit(self, *, scope: str, now: datetime) -> None:
        allowed = self._store.consume_rate_limit(
            scope_key=scope,
            limit_count=OTP_SEND_LIMIT,
            window_seconds=OTP_SEND_WINDOW_SECONDS,
            now=now,
        )
        if not allowed:
            raise ValueError("too many OTP requests, try again later")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_REGEX.match(normalized):
        raise ValueError("invalid email")
    return normalized


def normalize_phone(phone: str) -> str:
    normalized = phone.strip().replace(" ", "")
    if not PHONE_REGEX.match(normalized):
        raise ValueError("invalid phone")
    return normalized


def normalize_identifier(identifier: str) -> tuple[str, str]:
    raw = identifier.strip()
    if "@" in raw:
        return normalize_email(raw), "email"
    return normalize_phone(raw), "phone"


def validate_password_strength(password: str) -> None:
    if not PASSWORD_POLICY_REGEX.match(password):
        raise ValueError("password must be 8-128 chars and include at least one letter and one number")


def build_otp_response(*, otp_value: str, expires_at: datetime) -> dict[str, str]:
    payload: dict[str, str] = {
        "message": "OTP generated",
        "expiresAt": expires_at.isoformat(),
    }
    if settings.auth_expose_otp_in_response and settings.app_env != "production":
        payload["otp"] = otp_value
    return payload


auth_service = AuthService()
