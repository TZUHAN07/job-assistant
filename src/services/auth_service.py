import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.user import User
from src.models.auth_session import AuthSession

COOKIE_NAME = "job_assistant_access"
SESSION_SECONDS = 1800
ISSUER = "job-assistant"
AUDIENCE = "job-assistant-web"


def jwt_secret():
    secret = os.getenv("AUTH_JWT_SECRET", "")
    if len(secret.encode()) < 32:
        raise HTTPException(status_code=503, detail="登入服務尚未設定完成")
    return secret


def cookie_secure():
    value = os.getenv("AUTH_COOKIE_SECURE", "true").lower()
    if value not in {"true", "false"}:
        raise HTTPException(status_code=503, detail="登入服務設定不正確")
    if value == "false":
        origin = urlsplit(os.getenv("AUTH_ORIGIN", "http://127.0.0.1:8000"))
        if origin.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(status_code=503, detail="正式環境必須啟用安全 Cookie")
    return value == "true"


def require_same_origin(request: Request):
    expected = os.getenv("AUTH_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
    # 來源必須明確符合設定，不能以使用者可控制的 Host 標頭決定信任來源。
    if request.headers.get("origin") != expected or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="請從本站頁面操作")


def create_token(user_id: int, session_id: str, expires_at: datetime):
    return jwt.encode({
        "sub": str(user_id), "sid": session_id,
        "iat": datetime.now(timezone.utc), "exp": expires_at,
        "iss": ISSUER, "aud": AUDIENCE,
    }, jwt_secret(), algorithm="HS256")


def unauthorized():
    return HTTPException(status_code=401, detail="請重新登入")


@dataclass
class Principal:
    user: User
    session: AuthSession


async def get_current_principal(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)],
):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise unauthorized()
    try:
        claims = jwt.decode(token, jwt_secret(), algorithms=["HS256"],
                            issuer=ISSUER, audience=AUDIENCE,
                            options={"require": ["sub", "sid", "iat", "exp", "iss", "aud"]})
        if not isinstance(claims["sub"], str) or not claims["sub"].isascii() or not claims["sub"].isdigit():
            raise unauthorized()
        user_id = int(claims["sub"])
        if not 1 < user_id <= 2147483647:
            raise unauthorized()
        if not isinstance(claims["sid"], str) or len(claims["sid"]) != 64:
            raise unauthorized()
    except jwt.InvalidTokenError:
        raise unauthorized() from None
    row = (await db.execute(
        select(User, AuthSession).join(AuthSession, AuthSession.user_id == User.id)
        .where(User.id == user_id, User.is_active.is_(True),
               AuthSession.id == claims["sid"], AuthSession.revoked_at.is_(None),
               AuthSession.expires_at > datetime.now(timezone.utc))
    )).first()
    if row is None:
        raise unauthorized()
    return Principal(user=row[0], session=row[1])
