import pytest

from app.services.expense_service import ExpenseService


@pytest.fixture
def service() -> ExpenseService:
    return ExpenseService()


def test_equal_split_without_rows_auto_builds_with_drift_fix(service: ExpenseService) -> None:
    rows = service._validate_and_build_splits(
        amount=100.0,
        split_type="equal",
        splits=[],
        eligible_member_ids={"m1", "m2", "m3"},
    )

    assert len(rows) == 3
    assert round(sum((row[1] or 0) for row in rows), 2) == 100.0


def test_unequal_split_rejects_total_mismatch(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="sum of split amounts must equal expense amount"):
        service._validate_and_build_splits(
            amount=100.0,
            split_type="unequal",
            splits=[
                {"member_id": "m1", "amount_owed": 40},
                {"member_id": "m2", "amount_owed": 50},
            ],
            eligible_member_ids={"m1", "m2"},
        )


def test_custom_split_rejects_negative_non_excluded_amount(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="amount_owed is required for non-excluded members"):
        service._validate_and_build_splits(
            amount=100.0,
            split_type="custom",
            splits=[
                {"member_id": "m1", "amount_owed": 120},
                {"member_id": "m2", "amount_owed": -20},
            ],
            eligible_member_ids={"m1", "m2"},
        )


def test_percentage_split_requires_total_100(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="sum of split percentages must be 100"):
        service._validate_and_build_splits(
            amount=250.0,
            split_type="percentage",
            splits=[
                {"member_id": "m1", "percentage": 60},
                {"member_id": "m2", "percentage": 30},
            ],
            eligible_member_ids={"m1", "m2"},
        )


def test_percentage_split_allocates_amounts_with_excluded_rows(service: ExpenseService) -> None:
    rows = service._validate_and_build_splits(
        amount=200.0,
        split_type="percentage",
        splits=[
            {"member_id": "m1", "percentage": 50},
            {"member_id": "m2", "percentage": 50},
            {"member_id": "m3", "percentage": 0, "excluded": True},
        ],
        eligible_member_ids={"m1", "m2", "m3"},
    )

    assert rows[2] == ("m3", 0.0, 0.0, True)
    assert round(sum((row[1] or 0) for row in rows), 2) == 200.0


def test_selective_split_rejects_when_all_rows_excluded(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="at least one non-excluded split participant is required"):
        service._validate_and_build_splits(
            amount=90.0,
            split_type="selective",
            splits=[
                {"member_id": "m1", "excluded": True},
                {"member_id": "m2", "excluded": True},
            ],
            eligible_member_ids={"m1", "m2"},
        )


def test_split_rows_reject_duplicate_member_ids(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="duplicate split member_id"):
        service._validate_and_build_splits(
            amount=100.0,
            split_type="equal",
            splits=[
                {"member_id": "m1", "amount_owed": 50},
                {"member_id": "m1", "amount_owed": 50},
            ],
            eligible_member_ids={"m1"},
        )


def test_unsupported_split_type_raises(service: ExpenseService) -> None:
    with pytest.raises(ValueError, match="unsupported split type"):
        service._validate_and_build_splits(
            amount=100.0,
            split_type="mystery",
            splits=[{"member_id": "m1", "amount_owed": 100}],
            eligible_member_ids={"m1"},
        )
