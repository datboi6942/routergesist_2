from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import Cookie, HTTPException, Response, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from ..config import settings


SESSION_COOKIE = "rg_session"
serializer = URLSafeTimedSerializer(settings.secret_key or "routergeist-dev-key")


def create_session(response: Response, username: str) -> None:
    token = serializer.dumps({"u": username})
    max_age = int(timedelta(hours=12).total_seconds())
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=False,
        samesite="Lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def require_auth(rg_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)) -> str:
    if not rg_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = serializer.loads(rg_session, max_age=int(timedelta(hours=24).total_seconds()))
        return data.get("u")
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")


