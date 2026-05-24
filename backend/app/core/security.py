from __future__ import annotations

import base64
import hmac
import hashlib
import json
import secrets
from datetime import datetime, timezone

from app.core.settings import settings

_PBKDF2_ROUNDS = 120_000
_DEFAULT_DEV_JWT_SECRET = "tripwise-dev-jwt-secret-change-me"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"{_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        rounds_text, salt_hex, hash_hex = encoded_hash.split("$", 2)
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False

    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return secrets.compare_digest(computed, expected)


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def get_jwt_secret() -> str:
    if settings.jwt_secret and settings.jwt_secret.strip():
        return settings.jwt_secret.strip()
    if settings.app_env == "production":
        raise ValueError("JWT_SECRET is required in production")
    return _DEFAULT_DEV_JWT_SECRET


def sign_session_token(*, user_id: str, expires_at: datetime) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int(expires_at.replace(tzinfo=timezone.utc).timestamp()),
        "jti": secrets.token_urlsafe(18),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(get_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_session_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("invalid session token format") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(get_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)
    if not hmac.compare_digest(expected_sig_b64, signature_b64):
        raise ValueError("invalid session token signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid session token payload") from exc

    exp = int(payload.get("exp") or 0)
    if exp <= int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("session token expired")
    return payload


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)
