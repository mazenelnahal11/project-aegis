from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, HTTPException, status
from jose import JWTError, jwt

from .config import settings

COOKIE_NAME = "aegis_session"


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plaintext: str) -> bool:
    if not settings.admin_password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plaintext.encode("utf-8"),
            settings.admin_password_hash.encode("ascii"),
        )
    except (ValueError, TypeError):
        return False


def issue_token() -> str:
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def require_admin(aegis_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    if not aegis_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = decode_token(aegis_session)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    sub = payload.get("sub")
    if sub != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return sub
