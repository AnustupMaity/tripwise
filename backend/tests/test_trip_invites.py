from types import SimpleNamespace

import pytest

from app.services.trip_service import TripService
from app.services.trip_store import TripMemberRecord, TripRecord


class FakeTripStore:
    def __init__(self, *, trip_status: str = "planning", members: list[TripMemberRecord] | None = None) -> None:
        self.trip = TripRecord(
            trip_id="trip-1",
            name="Goa Sprint",
            created_by="profile-admin",
            status=trip_status,
            member_count=0,
        )
        self.members = list(members or [])
        self.member_count_updates: list[int] = []

    def get_trip(self, *, trip_id: str) -> TripRecord | None:
        if trip_id != self.trip.trip_id:
            return None
        return self.trip

    def list_trip_members(self, *, trip_id: str) -> list[TripMemberRecord]:
        if trip_id != self.trip.trip_id:
            return []
        return list(self.members)

    def set_trip_member_count(self, *, trip_id: str, member_count: int) -> TripRecord:
        self.trip.member_count = member_count
        self.member_count_updates.append(member_count)
        return self.trip

    def find_profile_by_identifier(self, identifier: str):
        return None

    def ensure_profile_for_identifier(self, *, identifier: str, display_name: str | None):
        return SimpleNamespace(profile_id="profile-invitee", name="Invitee")

    def add_trip_member(self, *, trip_id: str, profile_id: str | None, guest_identifier: str | None, role: str, invite_status: str) -> TripMemberRecord:
        member = TripMemberRecord(
            member_id=f"member-{len(self.members) + 1}",
            trip_id=trip_id,
            profile_id=profile_id,
            guest_identifier=guest_identifier,
            role=role,
            invite_status=invite_status,
        )
        self.members.append(member)
        return member

    def get_trip_member(self, *, member_id: str) -> TripMemberRecord | None:
        for member in self.members:
            if member.member_id == member_id:
                return member
        return None

    def reinvite_member(self, *, member_id: str) -> TripMemberRecord:
        member = self.get_trip_member(member_id=member_id)
        if member is None:
            raise ValueError("member not found")
        member.invite_status = "pending"
        return member


@pytest.fixture
def service() -> TripService:
    return TripService()


def test_invite_member_rejects_when_trip_closed(service: TripService) -> None:
    service._store = FakeTripStore(trip_status="closed")

    with pytest.raises(ValueError, match="trip is closed and no edits are allowed"):
        service.invite_member(trip_id="trip-1", identifier="new@tripwise.dev")


def test_invite_member_rejects_duplicate_identifier(service: TripService) -> None:
    members = [
        TripMemberRecord(
            member_id="member-1",
            trip_id="trip-1",
            profile_id=None,
            guest_identifier="dup@tripwise.dev",
            role="guest",
            invite_status="pending",
        )
    ]
    service._store = FakeTripStore(members=members)

    with pytest.raises(ValueError, match="identifier is already invited in this trip"):
        service.invite_member(trip_id="trip-1", identifier="dup@tripwise.dev")


def test_invite_all_requires_actor_to_be_accepted(service: TripService) -> None:
    service._store = FakeTripStore()
    service.resolve_member_for_identifier = lambda **_: {
        "memberId": "admin-member",
        "tripId": "trip-1",
        "profileId": "profile-admin",
        "role": "admin",
        "inviteStatus": "pending",
    }

    with pytest.raises(ValueError, match="actor is not an accepted trip member"):
        service.invite_all_members(
            trip_id="trip-1",
            identifiers=["a@tripwise.dev", "b@tripwise.dev"],
            actor_identifier="admin@tripwise.dev",
        )


def test_invite_all_returns_partial_success_and_skips(service: TripService) -> None:
    service._store = FakeTripStore()

    def fake_invite_member(*, trip_id: str, identifier: str) -> dict:
        if identifier == "blocked@tripwise.dev":
            raise ValueError("identifier is already invited in this trip")
        return {
            "memberId": f"member-{identifier}",
            "identifier": identifier,
            "mode": "registered_invite",
            "inviteStatus": "pending",
            "memberCount": 2,
        }

    service.invite_member = fake_invite_member

    result = service.invite_all_members(
        trip_id="trip-1",
        identifiers=["ok@tripwise.dev", "blocked@tripwise.dev", "ok@tripwise.dev"],
        actor_identifier=None,
    )

    assert result["summary"]["requested"] == 2
    assert result["summary"]["invitedCount"] == 1
    assert result["summary"]["skippedCount"] == 1
    assert result["skipped"][0]["identifier"] == "blocked@tripwise.dev"


def test_reinvite_member_rejects_accepted_members(service: TripService) -> None:
    members = [
        TripMemberRecord(
            member_id="member-accepted",
            trip_id="trip-1",
            profile_id="profile-2",
            guest_identifier=None,
            role="member",
            invite_status="accepted",
        )
    ]
    service._store = FakeTripStore(members=members)

    with pytest.raises(ValueError, match="accepted members cannot be re-invited"):
        service.reinvite_member(member_id="member-accepted")
