from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.services.auth_service import auth_service

router = APIRouter()


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=2, max_length=80)
    upi_id: str | None = None
    upi_number: str | None = None


class VerifyRegistrationRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class RequestOtpRequest(BaseModel):
    identifier: str


class VerifyOtpLoginRequest(BaseModel):
    identifier: str
    otp: str = Field(min_length=6, max_length=6)


class PasswordLoginRequest(BaseModel):
    identifier: str
    password: str = Field(min_length=8, max_length=128)


class VerifyForgotOtpRequest(BaseModel):
    identifier: str
    otp: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20)


class SessionValidationRequest(BaseModel):
    session_token: str


class CompleteProfileRequest(BaseModel):
    session_token: str
    name: str | None = None
    phone: str
    nickname: str | None = None
    email: EmailStr | None = None
    email_otp: str | None = None
    upi_id: str | None = None
    upi_number: str | None = None


class ProfileEmailOtpRequest(BaseModel):
    session_token: str
    email: EmailStr


class IdentifierStatusRequest(BaseModel):
    identifier: str


@router.post("/register/request-otp")
def register_request_otp(payload: RegisterRequest) -> dict[str, str]:
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="passwords do not match")

    try:
        return auth_service.request_registration_otp(
            name=payload.name,
            nickname=payload.nickname,
            email=str(payload.email),
            phone=payload.phone,
            password=payload.password,
            upi_id=payload.upi_id,
            upi_number=payload.upi_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/register/verify-otp")
def verify_register_otp(payload: VerifyRegistrationRequest) -> dict[str, str]:
    try:
        return auth_service.verify_registration_otp(email=str(payload.email), otp=payload.otp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login/request-otp")
def request_login_otp(payload: RequestOtpRequest) -> dict[str, str]:
    try:
        return auth_service.request_login_otp(identifier=payload.identifier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login/verify-otp")
def verify_login_otp(payload: VerifyOtpLoginRequest) -> dict[str, str]:
    try:
        return auth_service.verify_login_otp(identifier=payload.identifier, otp=payload.otp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login/password")
def password_login(payload: PasswordLoginRequest) -> dict[str, str]:
    try:
        return auth_service.login_with_password(
            identifier=payload.identifier,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/forgot-password/request-otp")
def forgot_password_request_otp(payload: RequestOtpRequest) -> dict[str, str]:
    try:
        return auth_service.request_forgot_password_otp(identifier=payload.identifier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/forgot-password/verify-otp")
def forgot_password_verify_otp(payload: VerifyForgotOtpRequest) -> dict[str, str]:
    try:
        return auth_service.verify_forgot_password_otp(
            identifier=payload.identifier,
            otp=payload.otp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/forgot-password/reset")
def forgot_password_reset(payload: ResetPasswordRequest) -> dict[str, str]:
    try:
        return auth_service.reset_password(
            reset_token=payload.reset_token,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/google/callback")
def google_callback(payload: GoogleLoginRequest) -> dict[str, str | bool]:
    try:
        return auth_service.login_with_google(id_token=payload.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/session/validate")
def validate_session(payload: SessionValidationRequest) -> dict[str, str | bool | None]:
    try:
        return auth_service.validate_session(token=payload.session_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/profile/complete")
def complete_profile(payload: CompleteProfileRequest) -> dict[str, str | bool]:
    try:
        return auth_service.update_profile_details(
            session_token=payload.session_token,
            name=payload.name,
            phone=payload.phone,
            upi_id=payload.upi_id,
            upi_number=payload.upi_number,
            nickname=payload.nickname,
            email=str(payload.email) if payload.email else None,
            email_otp=payload.email_otp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile/email/request-otp")
def request_profile_email_change_otp(payload: ProfileEmailOtpRequest) -> dict[str, str]:
    try:
        return auth_service.request_profile_email_change_otp(
            session_token=payload.session_token,
            email=str(payload.email),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/identifier/status")
def identifier_status(payload: IdentifierStatusRequest) -> dict[str, str | bool]:
    try:
        exists = auth_service.is_registered_identifier(identifier=payload.identifier)
        return {
            "identifier": payload.identifier,
            "registered": exists,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
