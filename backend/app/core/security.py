from __future__ import annotations

import hashlib
import secrets

_PBKDF2_ROUNDS = 120_000


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
