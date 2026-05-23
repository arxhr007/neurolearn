"""Authentication dependencies for API and web routes."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services.auth import decode_access_token, is_jwt_error
from app.services.session import get_session_user


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class UserContext:
    role: str
    user_id: int
    username: str
    student_id: str | None = None


def _context_from_session(session_user: dict) -> UserContext:
    return UserContext(
        role=str(session_user.get("role")),
        user_id=int(session_user.get("user_id") or 0),
        username=str(session_user.get("username") or ""),
        student_id=session_user.get("student_id"),
    )


def _context_from_token(token: str) -> UserContext:
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        if is_jwt_error(exc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        raise
    return UserContext(
        role=str(payload.get("role")),
        user_id=int(payload.get("user_id") or 0),
        username=str(payload.get("sub") or ""),
        student_id=payload.get("student_id"),
    )


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserContext:
    session_user = get_session_user(request)
    if session_user:
        return _context_from_session(session_user)

    if creds and creds.credentials:
        return _context_from_token(creds.credentials)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*roles: str):
    def _checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _checker
