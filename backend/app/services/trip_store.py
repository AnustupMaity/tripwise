from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from app.core.settings import settings

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


InviteStatus = Literal["pending", "accepted", "rejected"]
MemberRole = Literal["admin", "member", "guest"]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ProfileRecord:
    profile_id: str
    name: str
    email: str
    phone: str


@dataclass
class TripRecord:
    trip_id: str
    name: str
    created_by: str
    status: str
    member_count: int


@dataclass
class TripMemberRecord:
    member_id: str
    trip_id: str
    profile_id: str | None
    guest_identifier: str | None
    role: MemberRole
    invite_status: InviteStatus


class InMemoryTripStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles_by_id: dict[str, ProfileRecord] = {}
        self._profiles_by_email: dict[str, str] = {}
        self._profiles_by_phone: dict[str, str] = {}

        self._trips_by_id: dict[str, TripRecord] = {}
        self._trip_members_by_id: dict[str, TripMemberRecord] = {}

    def find_profile_by_identifier(self, identifier: str) -> ProfileRecord | None:
        with self._lock:
            profile_id = self._profiles_by_email.get(identifier) if is_email(identifier) else self._profiles_by_phone.get(identifier)
            if not profile_id:
                return None
            return self._profiles_by_id.get(profile_id)

    def ensure_profile_for_identifier(self, *, identifier: str, display_name: str | None) -> ProfileRecord:
        with self._lock:
            profile_id = self._profiles_by_email.get(identifier) if is_email(identifier) else self._profiles_by_phone.get(identifier)
            existing = self._profiles_by_id.get(profile_id) if profile_id else None
            if existing:
                return existing

            profile_id = uuid4().hex
            email = identifier if is_email(identifier) else f"phone-{identifier.strip('+')}@tripwise.local"
            phone = identifier if not is_email(identifier) else ""
            profile = ProfileRecord(
                profile_id=profile_id,
                name=display_name or default_name(identifier),
                email=email,
                phone=phone,
            )
            self._profiles_by_id[profile_id] = profile
            self._profiles_by_email[email] = profile_id
            if phone:
                self._profiles_by_phone[phone] = profile_id
            return profile

    def get_profile_by_id(self, *, profile_id: str) -> ProfileRecord | None:
        with self._lock:
            return self._profiles_by_id.get(profile_id)

    def create_trip(self, *, name: str, creator_profile_id: str, member_count: int) -> TripRecord:
        with self._lock:
            trip = TripRecord(
                trip_id=uuid4().hex,
                name=name,
                created_by=creator_profile_id,
                status="planning",
                member_count=member_count,
            )
            self._trips_by_id[trip.trip_id] = trip
            return trip

    def list_trips_by_creator(self, *, creator_profile_id: str) -> list[TripRecord]:
        with self._lock:
            return [t for t in self._trips_by_id.values() if t.created_by == creator_profile_id]

    def list_trips_for_identifier(self, *, identifier: str, profile_id: str | None) -> list[TripRecord]:
        normalized = normalize_member_identifier(identifier)
        with self._lock:
            trip_ids: set[str] = set()
            if profile_id:
                for trip in self._trips_by_id.values():
                    if trip.created_by == profile_id:
                        trip_ids.add(trip.trip_id)

            for member in self._trip_members_by_id.values():
                if profile_id and member.profile_id == profile_id:
                    trip_ids.add(member.trip_id)
                if member.guest_identifier and normalize_member_identifier(member.guest_identifier) == normalized:
                    trip_ids.add(member.trip_id)

            return [self._trips_by_id[trip_id] for trip_id in trip_ids if trip_id in self._trips_by_id]

    def get_trip(self, *, trip_id: str) -> TripRecord | None:
        with self._lock:
            return self._trips_by_id.get(trip_id)

    def set_trip_status(self, *, trip_id: str, status: str) -> TripRecord:
        with self._lock:
            trip = self._trips_by_id[trip_id]
            trip.status = status
            return trip

    def set_trip_name(self, *, trip_id: str, name: str) -> TripRecord:
        with self._lock:
            trip = self._trips_by_id[trip_id]
            trip.name = name
            return trip

    def set_trip_member_count(self, *, trip_id: str, member_count: int) -> TripRecord:
        with self._lock:
            trip = self._trips_by_id[trip_id]
            trip.member_count = member_count
            return trip

    def add_trip_member(self, *, trip_id: str, profile_id: str | None, guest_identifier: str | None, role: MemberRole, invite_status: InviteStatus) -> TripMemberRecord:
        with self._lock:
            member = TripMemberRecord(
                member_id=uuid4().hex,
                trip_id=trip_id,
                profile_id=profile_id,
                guest_identifier=guest_identifier,
                role=role,
                invite_status=invite_status,
            )
            self._trip_members_by_id[member.member_id] = member
            return member

    def list_trip_members(self, *, trip_id: str) -> list[TripMemberRecord]:
        with self._lock:
            return [m for m in self._trip_members_by_id.values() if m.trip_id == trip_id]

    def get_trip_member(self, *, member_id: str) -> TripMemberRecord | None:
        with self._lock:
            return self._trip_members_by_id.get(member_id)

    def update_trip_member_status(self, *, member_id: str, status: InviteStatus) -> TripMemberRecord:
        with self._lock:
            member = self._trip_members_by_id[member_id]
            member.invite_status = status
            return member

    def update_trip_member_role(self, *, member_id: str, role: MemberRole) -> TripMemberRecord:
        with self._lock:
            member = self._trip_members_by_id[member_id]
            member.role = role
            return member

    def reinvite_member(self, *, member_id: str) -> TripMemberRecord:
        with self._lock:
            member = self._trip_members_by_id[member_id]
            member.invite_status = "pending"
            return member

    def remove_trip_member(self, *, member_id: str) -> None:
        with self._lock:
            self._trip_members_by_id.pop(member_id, None)

    def link_guest_memberships_to_profile(self, *, identifier: str, profile_id: str) -> int:
        normalized = normalize_member_identifier(identifier)
        updated = 0
        with self._lock:
            for member in self._trip_members_by_id.values():
                if not member.guest_identifier:
                    continue
                if normalize_member_identifier(member.guest_identifier) != normalized:
                    continue
                member.profile_id = profile_id
                member.guest_identifier = None
                member.invite_status = "accepted"
                if member.role == "guest":
                    member.role = "member"
                updated += 1
        return updated


class PostgresTripStore:
    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        self._db_url = db_url

    def _conn(self):
        return psycopg.connect(self._db_url)

    def find_profile_by_identifier(self, identifier: str) -> ProfileRecord | None:
        column = "email" if is_email(identifier) else "phone"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                select id, name, email, coalesce(phone, '')
                from public.profiles
                where {column} = %s
                limit 1
                """,
                (identifier,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ProfileRecord(profile_id=str(row[0]), name=row[1], email=row[2], phone=row[3])

    def ensure_profile_for_identifier(self, *, identifier: str, display_name: str | None) -> ProfileRecord:
        existing = self.find_profile_by_identifier(identifier)
        if existing:
            return existing

        profile_id = str(uuid4())
        email = identifier if is_email(identifier) else f"phone-{identifier.strip('+')}@tripwise.local"
        phone = identifier if not is_email(identifier) else None
        name = display_name or default_name(identifier)

        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.profiles (id, name, email, phone)
                values (%s, %s, %s, %s)
                on conflict (email) do nothing
                """,
                (profile_id, name, email, phone),
            )
            conn.commit()

        found = self.find_profile_by_identifier(identifier if is_email(identifier) else (phone or ""))
        if not found:
            found = self.find_profile_by_identifier(email)
        if not found:
            raise ValueError("failed to create profile")
        return found

    def get_profile_by_id(self, *, profile_id: str) -> ProfileRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, name, email, coalesce(phone, '')
                from public.profiles
                where id = %s
                limit 1
                """,
                (profile_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ProfileRecord(profile_id=str(row[0]), name=row[1], email=row[2], phone=row[3])

    def create_trip(self, *, name: str, creator_profile_id: str, member_count: int) -> TripRecord:
        trip_id = str(uuid4())
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.trips (id, name, created_by, member_count)
                values (%s, %s, %s, %s)
                """,
                (trip_id, name, creator_profile_id, member_count),
            )
            conn.commit()
        return TripRecord(
            trip_id=trip_id,
            name=name,
            created_by=creator_profile_id,
            status="planning",
            member_count=member_count,
        )

    def list_trips_by_creator(self, *, creator_profile_id: str) -> list[TripRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, name, created_by, status, member_count
                from public.trips
                where created_by = %s
                order by created_at desc
                """,
                (creator_profile_id,),
            )
            rows = cur.fetchall()
            return [
                TripRecord(
                    trip_id=str(r[0]),
                    name=r[1],
                    created_by=str(r[2]),
                    status=str(r[3]),
                    member_count=int(r[4]),
                )
                for r in rows
            ]

    def list_trips_for_identifier(self, *, identifier: str, profile_id: str | None) -> list[TripRecord]:
        normalized = normalize_member_identifier(identifier)
        has_profile = profile_id is not None
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select t.id, t.name, t.created_by, t.status, t.member_count
                from public.trips t
                where
                    (
                        %s
                        and (
                            t.created_by = %s::uuid
                            or exists (
                                select 1
                                from public.trip_members tm
                                where tm.trip_id = t.id
                                  and tm.profile_id = %s::uuid
                            )
                        )
                    )
                    or exists (
                        select 1
                        from public.trip_members tm
                        where tm.trip_id = t.id
                          and lower(coalesce(tm.guest_identifier, '')) = %s
                    )
                order by t.created_at desc
                """,
                (has_profile, profile_id, profile_id, normalized),
            )
            rows = cur.fetchall()
            return [
                TripRecord(
                    trip_id=str(r[0]),
                    name=r[1],
                    created_by=str(r[2]),
                    status=str(r[3]),
                    member_count=int(r[4]),
                )
                for r in rows
            ]

    def get_trip(self, *, trip_id: str) -> TripRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, name, created_by, status, member_count
                from public.trips
                where id = %s
                limit 1
                """,
                (trip_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return TripRecord(
                trip_id=str(row[0]),
                name=row[1],
                created_by=str(row[2]),
                status=str(row[3]),
                member_count=int(row[4]),
            )

    def set_trip_status(self, *, trip_id: str, status: str) -> TripRecord:
        closed_at = "now()" if status in {"closed", "past"} else "null"
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                update public.trips
                set status = %s::public.trip_status,
                    updated_at = now(),
                    closed_at = {closed_at}
                where id = %s
                """,
                (status, trip_id),
            )
            conn.commit()
        trip = self.get_trip(trip_id=trip_id)
        if not trip:
            raise ValueError("trip not found")
        return trip

    def set_trip_name(self, *, trip_id: str, name: str) -> TripRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trips
                set name = %s,
                    updated_at = now()
                where id = %s
                """,
                (name, trip_id),
            )
            conn.commit()
        trip = self.get_trip(trip_id=trip_id)
        if not trip:
            raise ValueError("trip not found")
        return trip

    def set_trip_member_count(self, *, trip_id: str, member_count: int) -> TripRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trips
                set member_count = %s,
                    updated_at = now()
                where id = %s
                """,
                (member_count, trip_id),
            )
            conn.commit()
        trip = self.get_trip(trip_id=trip_id)
        if not trip:
            raise ValueError("trip not found")
        return trip

    def add_trip_member(self, *, trip_id: str, profile_id: str | None, guest_identifier: str | None, role: MemberRole, invite_status: InviteStatus) -> TripMemberRecord:
        member_id = str(uuid4())
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into public.trip_members (id, trip_id, profile_id, guest_identifier, role, invite_status, invited_by)
                values (%s, %s, %s, %s, %s::public.member_role, %s::public.invite_status, null)
                """,
                (member_id, trip_id, profile_id, guest_identifier, role, invite_status),
            )
            conn.commit()
        return TripMemberRecord(
            member_id=member_id,
            trip_id=trip_id,
            profile_id=profile_id,
            guest_identifier=guest_identifier,
            role=role,
            invite_status=invite_status,
        )

    def list_trip_members(self, *, trip_id: str) -> list[TripMemberRecord]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, profile_id, guest_identifier, role, invite_status
                from public.trip_members
                where trip_id = %s
                order by invited_at asc
                """,
                (trip_id,),
            )
            rows = cur.fetchall()
            result: list[TripMemberRecord] = []
            for r in rows:
                result.append(
                    TripMemberRecord(
                        member_id=str(r[0]),
                        trip_id=str(r[1]),
                        profile_id=str(r[2]) if r[2] else None,
                        guest_identifier=r[3],
                        role=str(r[4]),
                        invite_status=str(r[5]),
                    )
                )
            return result

    def get_trip_member(self, *, member_id: str) -> TripMemberRecord | None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                select id, trip_id, profile_id, guest_identifier, role, invite_status
                from public.trip_members
                where id = %s
                limit 1
                """,
                (member_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return TripMemberRecord(
                member_id=str(row[0]),
                trip_id=str(row[1]),
                profile_id=str(row[2]) if row[2] else None,
                guest_identifier=row[3],
                role=str(row[4]),
                invite_status=str(row[5]),
            )

    def update_trip_member_status(self, *, member_id: str, status: InviteStatus) -> TripMemberRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trip_members
                set invite_status = %s::public.invite_status, responded_at = now()
                where id = %s
                """,
                (status, member_id),
            )
            conn.commit()
        member = self.get_trip_member(member_id=member_id)
        if not member:
            raise ValueError("member not found")
        return member

    def update_trip_member_role(self, *, member_id: str, role: MemberRole) -> TripMemberRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trip_members
                set role = %s::public.member_role
                where id = %s
                """,
                (role, member_id),
            )
            conn.commit()
        member = self.get_trip_member(member_id=member_id)
        if not member:
            raise ValueError("member not found")
        return member

    def reinvite_member(self, *, member_id: str) -> TripMemberRecord:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trip_members
                set invite_status = 'pending'::public.invite_status, responded_at = null, invited_at = now()
                where id = %s
                """,
                (member_id,),
            )
            conn.commit()
        member = self.get_trip_member(member_id=member_id)
        if not member:
            raise ValueError("member not found")
        return member

    def remove_trip_member(self, *, member_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("delete from public.trip_members where id = %s", (member_id,))
            conn.commit()

    def link_guest_memberships_to_profile(self, *, identifier: str, profile_id: str) -> int:
        normalized = normalize_member_identifier(identifier)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update public.trip_members
                set profile_id = %s,
                    guest_identifier = null,
                    invite_status = 'accepted'::public.invite_status,
                    role = case when role = 'guest'::public.member_role then 'member'::public.member_role else role end
                where lower(coalesce(guest_identifier, '')) = %s
                """,
                (profile_id, normalized),
            )
            updated = cur.rowcount or 0
            conn.commit()
        return int(updated)


def is_email(identifier: str) -> bool:
    return bool(EMAIL_REGEX.match(identifier.strip().lower()))


def default_name(identifier: str) -> str:
    if is_email(identifier):
        return identifier.split("@", 1)[0]
    return f"user-{identifier[-4:]}"


def normalize_member_identifier(identifier: str) -> str:
    return identifier.strip().lower() if is_email(identifier) else identifier.strip().replace(" ", "")


def build_trip_store() -> InMemoryTripStore | PostgresTripStore:
    if settings.use_inmemory_stores:
        return InMemoryTripStore()
    if settings.supabase_db_url and psycopg is not None:
        try:
            with psycopg.connect(settings.supabase_db_url) as conn:
                conn.execute("select 1")
            return PostgresTripStore(settings.supabase_db_url)
        except Exception as exc:
            logging.getLogger("tripwise.db").warning("Falling back to in-memory trip store: %s", exc)
    return InMemoryTripStore()
