from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from ..auth import COOKIE_NAME, issue_token, verify_password
from ..config import settings

router = APIRouter(prefix="/api", tags=["auth"])


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    if not verify_password(body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad password")
    token = issue_token()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expire_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=False,  # dev: allow http://localhost
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}
