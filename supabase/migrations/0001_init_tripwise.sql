-- TripWise initial schema

create extension if not exists "pgcrypto";

create type public.trip_status as enum ('planning', 'active', 'closed', 'past');
create type public.member_role as enum ('admin', 'member', 'guest');
create type public.invite_status as enum ('pending', 'accepted', 'rejected');
create type public.split_type as enum ('equal', 'unequal', 'percentage', 'selective', 'custom');
create type public.expense_status as enum ('pending_approval', 'approved', 'rejected');
create type public.dispute_status as enum ('open', 'in_review', 'resolved');
create type public.payment_method as enum ('upi', 'bank', 'cash', 'manual');
create type public.payment_status as enum ('pending', 'paid');

create table if not exists public.profiles (
    id uuid primary key default gen_random_uuid(),
    auth_user_id uuid unique,
    name text not null,
    phone text unique,
    email text unique not null,
    nickname text,
    upi_id text,
    upi_number text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.trips (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_by uuid not null references public.profiles(id),
    status public.trip_status not null default 'planning',
    member_count int not null default 1,
    closed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.trip_members (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references public.trips(id) on delete cascade,
    profile_id uuid references public.profiles(id),
    guest_identifier text,
    role public.member_role not null default 'member',
    invite_status public.invite_status not null default 'pending',
    invited_by uuid references public.profiles(id),
    invited_at timestamptz not null default now(),
    responded_at timestamptz,
    unique (trip_id, profile_id)
);

create table if not exists public.expenses (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references public.trips(id) on delete cascade,
    amount numeric(12,2) not null check (amount > 0),
    description text not null,
    created_by uuid not null references public.profiles(id),
    split_type public.split_type not null,
    status public.expense_status not null default 'pending_approval',
    approved_by uuid references public.profiles(id),
    approved_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.expense_payers (
    id uuid primary key default gen_random_uuid(),
    expense_id uuid not null references public.expenses(id) on delete cascade,
    member_id uuid not null references public.trip_members(id),
    amount_paid numeric(12,2) not null check (amount_paid >= 0)
);

create table if not exists public.expense_splits (
    id uuid primary key default gen_random_uuid(),
    expense_id uuid not null references public.expenses(id) on delete cascade,
    member_id uuid not null references public.trip_members(id),
    amount_owed numeric(12,2),
    percentage numeric(5,2),
    excluded boolean not null default false,
    created_at timestamptz not null default now(),
    unique (expense_id, member_id)
);

create table if not exists public.disputes (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references public.trips(id) on delete cascade,
    expense_id uuid not null references public.expenses(id) on delete cascade,
    raised_by uuid not null references public.profiles(id),
    comment text not null,
    status public.dispute_status not null default 'open',
    resolved_by uuid references public.profiles(id),
    resolved_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.payments (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid not null references public.trips(id) on delete cascade,
    from_member_id uuid not null references public.trip_members(id),
    to_member_id uuid not null references public.trip_members(id),
    amount numeric(12,2) not null check (amount > 0),
    method public.payment_method not null default 'manual',
    status public.payment_status not null default 'pending',
    paid_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.profiles(id) on delete cascade,
    channel text not null,
    event_type text not null,
    payload jsonb not null,
    delivered_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    trip_id uuid references public.trips(id) on delete cascade,
    actor_profile_id uuid references public.profiles(id),
    action text not null,
    entity_type text not null,
    entity_id uuid,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_trips_created_by on public.trips(created_by);
create index if not exists idx_trip_members_trip_id on public.trip_members(trip_id);
create index if not exists idx_expenses_trip_id on public.expenses(trip_id);
create index if not exists idx_payments_trip_id on public.payments(trip_id);
create index if not exists idx_notifications_profile_id on public.notifications(profile_id);
