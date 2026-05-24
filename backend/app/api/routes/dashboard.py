from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def get_dashboard() -> dict:
    return {
        "currentTrips": [],
        "pastTripsCount": 0,
        "quickActions": ["add_trip", "add_expense"],
    }
