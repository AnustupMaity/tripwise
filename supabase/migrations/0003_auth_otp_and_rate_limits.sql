-- Persist OTP, reset token, pending registration, and OTP rate limits

create table if not exists public.auth_pending_registrations (
    email text primary key,
    name text not null,
    nickname text not null,
    phone text not null,
    upi_id text,
    upi_number text,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.auth_otp_challenges (
    identifier text not null,
    purpose text not null,
    otp_hash text not null,
    expires_at timestamptz not null,
    attempts int not null default 0,
    created_at timestamptz not null default now(),
    primary key (identifier, purpose)
);

create index if not exists idx_auth_otp_challenges_expires_at
    on public.auth_otp_challenges(expires_at);

create table if not exists public.auth_password_reset_tokens (
    token_hash text primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_auth_password_reset_tokens_expires_at
    on public.auth_password_reset_tokens(expires_at);

create table if not exists public.auth_rate_limits (
    scope_key text primary key,
    window_started_at timestamptz not null,
    count int not null default 0,
    updated_at timestamptz not null default now()
);
