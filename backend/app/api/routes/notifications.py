from fastapi import APIRouter, Depends

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.services.in_app_notification_service import in_app_notification_service
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/jobs")
def list_notification_jobs(limit: int = 200) -> dict:
    return notification_service.list_jobs(limit=limit)


@router.get("/in-app")
def list_in_app_notifications(identifier: str, limit: int = 100, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, identifier, field_name="identifier")
    return in_app_notification_service.list_for_identifier(identifier=identifier, limit=limit)
