from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import auth_service
from app.api.routes import expenses as expenses_routes
from app.api.routes import trips as trips_routes


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        auth_service,
        "validate_session",
        lambda token: {
            "userId": "user-1",
            "email": "owner@tripwise.dev",
            "name": "Owner",
            "nickname": "owner",
            "phone": "+911234567890",
        },
    )
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"x-session-token": "test-session-token"}


def test_create_trip_route_accepts_frontend_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_create_trip(**kwargs):
        captured.update(kwargs)
        return {"trip": {"trip_id": "trip-1", "name": kwargs["trip_name"]}, "invites": []}

    monkeypatch.setattr(trips_routes.trip_service, "create_trip", fake_create_trip)

    response = client.post(
        "/api/v1/trips/",
        json={
            "name": "Goa Weekend",
            "creator_identifier": "owner@tripwise.dev",
            "creator_name": "Owner",
            "creation_mode": "dynamic",
            "member_entries": [
                {"name": "A", "email": "a@tripwise.dev"},
                {"name": "B", "email": "b@tripwise.dev"},
            ],
        },
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert captured["trip_name"] == "Goa Weekend"
    assert captured["creator_identifier"] == "owner@tripwise.dev"
    assert captured["creation_mode"] == "dynamic"
    assert len(captured["member_entries"]) == 2


def test_create_trip_rejects_identifier_mismatch(client: TestClient) -> None:
    response = client.post(
        "/api/v1/trips/",
        json={
            "name": "Mismatch",
            "creator_identifier": "other@tripwise.dev",
            "creation_mode": "dynamic",
            "member_entries": [{"name": "A", "email": "a@tripwise.dev"}],
        },
        headers=_auth_headers(),
    )

    assert response.status_code == 403
    assert "does not match authenticated user" in response.text


def test_list_trips_without_trailing_slash_redirects(client: TestClient) -> None:
    response = client.get("/api/v1/trips", headers=_auth_headers(), follow_redirects=False)
    assert response.status_code == 307


def test_list_trips_with_trailing_slash_returns_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        trips_routes.trip_service,
        "list_trips",
        lambda creator_identifier: {
            "trips": [
                {
                    "trip_id": "trip-1",
                    "name": "Goa Weekend",
                    "status": "planning",
                    "member_count": 3,
                    "my_role": "admin",
                }
            ]
        },
    )

    response = client.get("/api/v1/trips/", headers=_auth_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["trips"][0]["trip_id"] == "trip-1"


@pytest.mark.parametrize(
    "split_type,splits",
    [
        ("equal", []),
        (
            "unequal",
            [
                {"member_id": "m1", "amount_owed": 60, "excluded": False},
                {"member_id": "m2", "amount_owed": 40, "excluded": False},
            ],
        ),
        (
            "percentage",
            [
                {"member_id": "m1", "percentage": 50, "excluded": False},
                {"member_id": "m2", "percentage": 50, "excluded": False},
            ],
        ),
        (
            "selective",
            [
                {"member_id": "m1", "excluded": False},
                {"member_id": "m2", "excluded": True},
            ],
        ),
        (
            "custom",
            [
                {"member_id": "m1", "amount_owed": 75, "excluded": False},
                {"member_id": "m2", "amount_owed": 25, "excluded": False},
            ],
        ),
    ],
)
def test_add_expense_supports_all_split_types(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    split_type: str,
    splits: list[dict],
) -> None:
    captured: dict = {}

    def fake_add_expense(**kwargs):
        captured.update(kwargs)
        return {"expense": {"expense_id": "exp-1", "split_type": kwargs["split_type"]}}

    monkeypatch.setattr(expenses_routes.expense_service, "add_expense", fake_add_expense)

    response = client.post(
        "/api/v1/expenses/",
        json={
            "trip_id": "trip-1",
            "actor_identifier": "owner@tripwise.dev",
            "amount": 100,
            "description": f"Expense {split_type}",
            "paid_by": [{"member_id": "m1", "amount_paid": 100}],
            "split_type": split_type,
            "splits": splits,
        },
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert captured["split_type"] == split_type
    assert captured["trip_id"] == "trip-1"


def test_add_expense_rejects_identifier_mismatch(client: TestClient) -> None:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "trip_id": "trip-1",
            "actor_identifier": "other@tripwise.dev",
            "amount": 100,
            "description": "Lunch",
            "paid_by": [{"member_id": "m1", "amount_paid": 100}],
            "split_type": "equal",
            "splits": [],
        },
        headers=_auth_headers(),
    )

    assert response.status_code == 403
    assert "does not match authenticated user" in response.text
