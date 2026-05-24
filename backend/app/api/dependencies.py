from __future__ import annotations

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.services.auth_service import auth_service


class SessionPrincipal(BaseModel):
    user_id: str
    name: str | None = None
    nickname: str | None = None
    email: str
    phone: str | None = None

    def matches_identifier(self, identifier: str) -> bool:
        normalized = identifier.strip().lower()
        if not normalized:
            return False
        allowed = {self.email.strip().lower()}
        if self.phone:
            allowed.add(self.phone.strip().lower())
        return normalized in allowed


def _extract_session_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    token = request.headers.get("x-session-token", "").strip()
    return token or None


def require_session(request: Request) -> SessionPrincipal:
    token = _extract_session_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing session token",
        )

    try:
        session_data = auth_service.validate_session(token=token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user_id = str(session_data.get("userId") or "").strip()
    email = str(session_data.get("email") or "").strip()
    name = str(session_data.get("name") or "").strip() or None
    nickname = str(session_data.get("nickname") or "").strip() or None
    phone = str(session_data.get("phone") or "").strip() or None
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session principal",
        )

    return SessionPrincipal(user_id=user_id, name=name, nickname=nickname, email=email, phone=phone)


def ensure_identifier_matches(principal: SessionPrincipal, identifier: str, *, field_name: str = "identifier") -> None:
    if not principal.matches_identifier(identifier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{field_name} does not match authenticated user",
        )
