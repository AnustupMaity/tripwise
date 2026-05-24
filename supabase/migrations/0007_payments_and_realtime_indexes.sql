-- Payment history and settlement query indexes

create index if not exists idx_payments_trip_created
    on public.payments(trip_id, created_at desc);

create index if not exists idx_payments_trip_status
    on public.payments(trip_id, status);

create index if not exists idx_payments_from_to
    on public.payments(trip_id, from_member_id, to_member_id);
