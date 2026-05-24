-- Dispute workflow enhancements

alter table public.disputes
    add column if not exists disputed_amount numeric(12,2),
    add column if not exists reviewed_by uuid references public.profiles(id),
    add column if not exists reviewed_at timestamptz,
    add column if not exists resolution_comment text;

create table if not exists public.dispute_comments (
    id uuid primary key,
    dispute_id uuid not null references public.disputes(id) on delete cascade,
    author_profile_id uuid not null references public.profiles(id),
    comment text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_disputes_trip_status_created
    on public.disputes(trip_id, status, created_at desc);

create index if not exists idx_dispute_comments_dispute_created
    on public.dispute_comments(dispute_id, created_at asc);
