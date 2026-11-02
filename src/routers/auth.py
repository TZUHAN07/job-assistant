import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.database import get_db
from src.limiter import limiter
from src.models.user import User
from src.schemas.auth import RegisterRequest, RegisterResponse, UserPublic
from src.services.password_service import hash_password, verify_password, DUMMY_HASH
from src.models.auth_session import AuthSession
from src.schemas.auth import LoginRequest, AuthResponse
from src.services.auth_service import (
    COOKIE_NAME, SESSION_SECONDS, cookie_secure, jwt_secret, create_token,
    require_same_origin, get_current_principal, Principal,
)

logger = logging.getLogger(__name__)


class AuthRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                # FastAPI 預設會附回 input；註冊錯誤不可回傳原始密碼。
                return JSONResponse(status_code=422, content={"detail": [
                    {"loc": error["loc"], "type": error["type"], "msg": "欄位格式不正確"}
                    for error in exc.errors()
                ]})
        return handler


router = APIRouter(prefix="/auth", tags=["Auth"], route_class=AuthRoute)


@router.post("/register", response_model=RegisterResponse, status_code=201, dependencies=[Depends(require_same_origin)])
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest,
                   db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        existing = await db.scalar(select(User.id).where(User.email == str(body.email)))
        if existing is not None:
            raise HTTPException(status_code=409, detail="此 Email 已註冊")
        # 密碼雜湊耗 CPU，移到執行緒，避免卡住其他非同步請求。
        await db.rollback()
        password_hash = await run_in_threadpool(hash_password, body.password.get_secret_value())
        user = User(email=str(body.email), password_hash=password_hash)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        response = RegisterResponse(message="註冊成功", data=UserPublic.model_validate(user))
        await db.commit()
        return response
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        # 同時送出兩次註冊時，仍由資料庫唯一限制擋住重複帳號。
        await db.rollback()
        raise HTTPException(status_code=409, detail="帳號無法建立，請確認 Email 是否已註冊") from None
    except Exception as exc:
        await db.rollback()
        logger.error("Registration failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="註冊失敗，請稍後再試") from None


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(require_same_origin)])
@limiter.limit("5/minute")
async def login(request: Request, response: Response, body: LoginRequest,
                db: Annotated[AsyncSession, Depends(get_db)]):
    jwt_secret()
    secure = cookie_secure()
    try:
        user = await db.scalar(select(User).where(User.email == str(body.email)).with_for_update())
        valid = await run_in_threadpool(verify_password, body.password.get_secret_value(),
                                       user.password_hash if user else DUMMY_HASH)
        if user is None or not valid or not user.is_active or user.id == 1:
            raise HTTPException(status_code=401, detail="Email 或密碼不正確")
        session = AuthSession(id=secrets.token_hex(32), user_id=user.id,
                              expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS))
        token = create_token(user.id, session.id, session.expires_at)
        result = AuthResponse(message="登入成功", data=UserPublic.model_validate(user))
        db.add(session)
        await db.commit()
        # 交易成功後才發 Cookie，避免發出不存在的登入紀錄。
        response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=secure, samesite="lax", path="/")
        response.headers["Cache-Control"] = "no-store"
        return result
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("Login failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="登入失敗，請稍後再試") from None


@router.get("/me", response_model=AuthResponse)
async def me(response: Response, principal: Annotated[Principal, Depends(get_current_principal)]):
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(message="身分查詢成功", data=UserPublic.model_validate(principal.user))


@router.post("/logout", dependencies=[Depends(require_same_origin)])
async def logout(response: Response, principal: Annotated[Principal, Depends(get_current_principal)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    secure = cookie_secure()
    try:
        principal.session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Logout failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="登出失敗，請稍後再試") from None
    response.delete_cookie(COOKIE_NAME, path="/", secure=secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "已登出"}
