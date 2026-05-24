-- Trip member invite flow support indexes/constraints

create unique index if not exists uq_trip_members_guest_identifier
    on public.trip_members(trip_id, guest_identifier)
    where guest_identifier is not null;

create index if not exists idx_trip_members_trip_status
    on public.trip_members(trip_id, invite_status);
