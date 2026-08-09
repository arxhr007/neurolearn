"""Session and CSRF helpers for web routes."""

import secrets

from fastapi import HTTPException, Request, status


def set_session_user(request: Request, user: dict) -> None:
    request.session["user"] = user


def get_session_user(request: Request) -> dict | None:
    return request.session.get("user")


def clear_session(request: Request) -> None:
    request.session.pop("user", None)
    request.session.pop("csrf_token", None)


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(16)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, token: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not token or expected != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
