-- TripWise auth persistence schema additions

alter table public.profiles
    add column if not exists password_hash text,
    add column if not exists google_sub text unique;

create table if not exists public.auth_sessions (
    token_hash text primary key,
    user_id uuid not null references public.profiles(id) on delete cascade,
    expires_at timestamptz not null,
    last_active_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_auth_sessions_user_id on public.auth_sessions(user_id);
create index if not exists idx_auth_sessions_expires_at on public.auth_sessions(expires_at);
