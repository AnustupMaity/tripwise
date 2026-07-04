from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        # Keep explicitly exported environment variables higher priority.
        os.environ.setdefault(key, value.strip())


_load_dotenv_file()


def _first_env(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip() != "":
            return value
    return None


app_env = os.getenv("APP_ENV", "development")
default_cors_allowed_origins = "https://tripwise-liard.vercel.app,http://localhost:3000,http://127.0.0.1:3000"
default_cors_allowed_origin_regex = r"https://.*\.vercel\.app"


@dataclass(frozen=True)
class Settings:
    app_env: str
    supabase_db_url: str | None
    use_inmemory_stores: bool
    app_base_url: str
    report_output_dir: str
    brevo_api_key: str | None
    brevo_sender_email: str | None
    brevo_sender_name: str | None
    google_client_id: str | None
    google_client_secret: str | None
    whatsapp_webhook_url: str | None
    push_webhook_url: str | None
    notification_retry_max_attempts: int
    notification_retry_base_delay_seconds: int
    jwt_secret: str | None
    auth_expose_otp_in_response: bool
    cors_allowed_origins: list[str]
    cors_allowed_origin_regex: str | None
    request_audit_log_enabled: bool
    api_rate_limit_enabled: bool
    api_rate_limit_per_minute: int
    api_rate_limit_auth_per_5_min: int
    api_rate_limit_report_per_min: int


settings = Settings(
    app_env=app_env,
    supabase_db_url=os.getenv("SUPABASE_DB_URL"),
    use_inmemory_stores=os.getenv("USE_INMEMORY_STORES", "false").strip().lower() in {"1", "true", "yes"},
    app_base_url=os.getenv("APP_BASE_URL", "http://localhost:8000"),
    report_output_dir=os.getenv("REPORT_OUTPUT_DIR", "generated_reports"),
    brevo_api_key=_first_env("BREVO_API_KEY", "BROVO_API_KEY"),
    brevo_sender_email=_first_env("BREVO_SENDER_EMAIL", "BROVO_SENDER_EMAIL"),
    brevo_sender_name=_first_env("BREVO_SENDER_NAME", "BROVO_SENDER_NAME") or "TripWise",
    google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
    google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    whatsapp_webhook_url=os.getenv("WHATSAPP_WEBHOOK_URL"),
    push_webhook_url=os.getenv("PUSH_WEBHOOK_URL"),
    notification_retry_max_attempts=int(os.getenv("NOTIFICATION_RETRY_MAX_ATTEMPTS", "3")),
    notification_retry_base_delay_seconds=int(os.getenv("NOTIFICATION_RETRY_BASE_DELAY_SECONDS", "5")),
    jwt_secret=os.getenv("JWT_SECRET"),
    auth_expose_otp_in_response=os.getenv("AUTH_EXPOSE_OTP_IN_RESPONSE", "true").strip().lower() in {"1", "true", "yes"},
    cors_allowed_origins=[
        o.strip()
        for o in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            default_cors_allowed_origins,
        ).split(",")
        if o.strip()
    ],
    cors_allowed_origin_regex=os.getenv("CORS_ALLOWED_ORIGIN_REGEX", default_cors_allowed_origin_regex),
    request_audit_log_enabled=os.getenv("REQUEST_AUDIT_LOG_ENABLED", "true").strip().lower() in {"1", "true", "yes"},
    api_rate_limit_enabled=os.getenv("API_RATE_LIMIT_ENABLED", "true").strip().lower() in {"1", "true", "yes"},
    api_rate_limit_per_minute=int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "600")),
    api_rate_limit_auth_per_5_min=int(os.getenv("API_RATE_LIMIT_AUTH_PER_5_MIN", "300")),
    api_rate_limit_report_per_min=int(os.getenv("API_RATE_LIMIT_REPORT_PER_MIN", "60")),
)
