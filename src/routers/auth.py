import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
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
from src.services.password_service import hash_password

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


@router.post("/register", response_model=RegisterResponse, status_code=201)
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
