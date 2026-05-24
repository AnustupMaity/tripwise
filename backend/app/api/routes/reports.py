from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.dependencies import SessionPrincipal, ensure_identifier_matches, require_session
from app.core.settings import settings
from app.services.report_service import report_service

router = APIRouter()


class GenerateReportRequest(BaseModel):
    trip_id: str
    actor_identifier: str
    report_type: str = Field(description="summary|detailed|settlement|expense_breakdown")
    format: str = Field(description="pdf|excel|json")
    email_to: list[str] = Field(default_factory=list)


class SendReportEmailRequest(BaseModel):
    trip_id: str
    actor_identifier: str
    recipients: list[str] = Field(default_factory=list)

class CreatePublicSummaryLinkRequest(BaseModel):
    trip_id: str
    actor_identifier: str


@router.post("/generate")
def generate_report(payload: GenerateReportRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return report_service.generate_report(
            trip_id=payload.trip_id,
            actor_identifier=payload.actor_identifier,
            report_type=payload.report_type,
            format=payload.format,
            email_to=payload.email_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/")
def list_reports(trip_id: str) -> dict:
    return report_service.list_reports(trip_id=trip_id)


@router.post("/{report_id}/send-email")
def send_report_email(report_id: str, payload: SendReportEmailRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return report_service.send_report_email(
            trip_id=payload.trip_id,
            report_id=report_id,
            actor_identifier=payload.actor_identifier,
            recipients=payload.recipients,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/public/summary-link")
def create_public_summary_link(payload: CreatePublicSummaryLinkRequest, principal: SessionPrincipal = Depends(require_session)) -> dict:
    ensure_identifier_matches(principal, payload.actor_identifier, field_name="actor_identifier")
    try:
        return report_service.create_public_summary_link(
            trip_id=payload.trip_id,
            actor_identifier=payload.actor_identifier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/public/summary/{token}")
def get_public_summary(token: str) -> dict:
    try:
        return report_service.get_public_summary(token=token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/files/{filename}")
def download_report_file(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    file_path = Path(settings.report_output_dir) / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="report file not found")
    return FileResponse(path=str(file_path), filename=safe_name)
