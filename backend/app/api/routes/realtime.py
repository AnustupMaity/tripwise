from fastapi import APIRouter

from app.services.realtime_service import realtime_service

router = APIRouter()


@router.get("/{trip_id}")
def trip_events(trip_id: str, limit: int = 100) -> dict:
    return realtime_service.list_trip_events(trip_id=trip_id, limit=limit)
