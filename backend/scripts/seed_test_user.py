from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from app.core.security import generate_token, hash_password
from app.services.auth_service import normalize_email, normalize_phone
from app.services.auth_store import build_auth_store, hash_session_token

SESSION_VALID_DAYS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or update a local E2E test user and mint a session token.",
    )
    parser.add_argument("--email", required=True, help="Test user email")
    parser.add_argument("--password", required=True, help="Test user password")
    parser.add_argument("--name", default="E2E User", help="Display name")
    parser.add_argument("--nickname", default="e2e", help="Nickname")
    parser.add_argument("--phone", default="+911111111111", help="Phone number")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = build_auth_store()

    email = normalize_email(args.email)
    phone = normalize_phone(args.phone)
    password_hash = hash_password(args.password)

    user = store.find_user_by_identifier(email, "email")
    if user is None:
        user = store.create_user(
            name=args.name,
            nickname=args.nickname,
            email=email,
            phone=phone,
            upi_id=None,
            upi_number=None,
            password_hash=password_hash,
            google_sub=None,
        )
        action = "created"
    else:
        store.update_password_hash(user_id=user.user_id, password_hash=password_hash)
        # Keep profile usable for flows that expect phone/nickname.
        try:
            user = store.complete_profile(
                user_id=user.user_id,
                phone=phone,
                upi_id=user.upi_id,
                upi_number=user.upi_number,
                nickname=args.nickname,
            )
        except ValueError:
            # Ignore phone collisions and continue with password update.
            user = store.find_user_by_id(user.user_id) or user
        action = "updated"

    now = datetime.now(timezone.utc)
    session_token = generate_token(32)
    store.create_session(
        token_hash=hash_session_token(session_token),
        user_id=user.user_id,
        expires_at=now + timedelta(days=SESSION_VALID_DAYS),
        last_active_at=now,
    )

    print(f"seed_status={action}")
    print(f"email={user.email}")
    print(f"user_id={user.user_id}")
    print(f"password={args.password}")
    print(f"session_token={session_token}")
    print(f"session_expires_at={(now + timedelta(days=SESSION_VALID_DAYS)).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
