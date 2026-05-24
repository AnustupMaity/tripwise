-- Reports persistence support

create table if not exists public.reports (
    id uuid primary key,
    trip_id uuid not null references public.trips(id) on delete cascade,
    generated_by uuid not null references public.trip_members(id),
    report_type text not null,
    format text not null,
    file_url text not null,
    email_sent_to text,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create index if not exists idx_reports_trip_created
    on public.reports(trip_id, created_at desc);

create index if not exists idx_reports_expires
    on public.reports(expires_at);
