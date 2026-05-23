"""Authentication helpers for password hashing and JWT issuance."""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings


"""
Use a pure-Python, dependency-free hashing scheme by default to avoid
platform-specific compiled dependencies like `bcrypt` which caused
startup failures in some Windows environments. `pbkdf2_sha256` is
well-supported by passlib and does not require external libraries.
"""
_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def create_access_token(
    username: str,
    role: str,
    user_id: int,
    student_id: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": username,
        "email": username,
        "role": role,
        "user_id": user_id,
        "student_id": student_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def is_jwt_error(exc: Exception) -> bool:
    return isinstance(exc, JWTError)
