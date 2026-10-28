import asyncio
import logging
import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from google import genai
from google.genai import errors, types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.limiter import limiter
from src.models import InterviewSet, Job, Matching, Resume
from src.schemas.interview import (
    InterviewLatestResponse,
    InterviewSetSummary,
    InterviewGetResponse,
    InterviewGenerateRequest,
    InterviewGenerateResponse,
    InterviewReport,
    InterviewSetRecord,
)
from src.services.interview_service import run_interview

router = APIRouter(prefix="/interview-sets", tags=["Interview"])
logger = logging.getLogger(__name__)
db_dependency = Annotated[AsyncSession, Depends(get_db)]


def get_current_user_id() -> int:
    # MVP 尚未接登入；不能讓前端自行指定資料擁有者。
    return 1


async def get_interview_client():
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="面試題生成服務尚未設定")
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    try:
        yield client
    finally:
        await asyncio.to_thread(client.close)


@router.post("/generate", response_model=InterviewGenerateResponse, status_code=201)
@limiter.limit("20/hour")
async def generate_interview_set(
    request: Request,
    body: InterviewGenerateRequest,
    db: db_dependency,
    user_id: Annotated[int, Depends(get_current_user_id)],
    client: Annotated[genai.Client, Depends(get_interview_client)],
):
    """依匹配紀錄生成並保存五題。每次成功呼叫新增一組，不覆蓋既有題組。"""
    try:
        # 同時限制來源資料的擁有者，避免只檢查 matching 而漏掉履歷與職缺。
        source = (
            await db.execute(
                select(
                    Resume.processed_at,
                    Resume.parsed_data,
                    Job.processed_at,
                    Job.parsed_data,
                )
                .select_from(Matching)
                .join(Resume, Resume.id == Matching.resume_id)
                .join(Job, Job.id == Matching.job_id)
                .where(
                    Matching.id == body.matching_id,
                    Matching.user_id == user_id,
                    Resume.user_id == user_id,
                    Job.user_id == user_id,
                )
            )
        ).one_or_none()
        if source is None:
            raise HTTPException(status_code=404, detail="找不到可使用的匹配紀錄")
        if not all(source):
            raise HTTPException(status_code=409, detail="履歷或職缺尚未完成解析")
        # 等待 AI 時不持有這個查詢交易；service 的工具會自行管理查詢 session。
        await db.rollback()

        try:
            artifact = await run_interview(client, body.matching_id, user_id=user_id)
            report = InterviewReport.model_validate(artifact)
            if report.matching_id != body.matching_id:
                raise ValueError("Generated report belongs to another matching")
        except (TimeoutError, httpx.TimeoutException):
            raise HTTPException(
                status_code=504, detail="面試題生成逾時，請稍後再試"
            ) from None
        except (ValueError, errors.APIError, httpx.HTTPError) as exc:
            # 不把含履歷或上游回應的例外內容寫入日誌／HTTP 回應。
            logger.warning("Interview generation failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=502, detail="面試題生成或驗證失敗，未儲存題組"
            ) from None

        # 生成期間資料可能被刪除；存檔前重新確認，並鎖到交易完成。
        matching = await db.scalar(
            select(Matching.id)
            .where(
                Matching.id == body.matching_id,
                Matching.user_id == user_id,
            )
            .with_for_update()
        )
        if matching is None:
            raise HTTPException(status_code=404, detail="匹配紀錄已不存在，未儲存題組")
        row = InterviewSet(
            user_id=user_id,
            matching_id=body.matching_id,
            report=report.model_dump(mode="json"),
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        # 先建立可回傳的資料，再 commit，避免回應格式錯誤卻已寫入成功。
        response = InterviewGenerateResponse(
            message="面試題生成成功", data=InterviewSetRecord.model_validate(row)
        )
        await db.commit()
        return response
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("Interview request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail="伺服器處理失敗，請稍後再試"
        ) from None


@router.get("/latest", response_model=InterviewLatestResponse)
@limiter.limit("100/minute")
async def get_latest_interview_set(
    request: Request,
    matching_id: Annotated[int, Query(gt=0)],
    db: db_dependency,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    """回傳最近題組摘要；matching 存在但沒有題組時，data 為 null。"""
    try:
        matching = await db.scalar(
            select(Matching.id).where(
                Matching.id == matching_id,
                Matching.user_id == user_id,
            )
        )
        if matching is None:
            raise HTTPException(status_code=404, detail="找不到可使用的匹配紀錄")
        # 只讀摘要欄位，不載入整份履歷快照；同時間建立時以 ID 決定順序。
        row = (
            await db.execute(
                select(
                    InterviewSet.id,
                    InterviewSet.matching_id,
                    InterviewSet.created_at,
                )
                .where(
                    InterviewSet.matching_id == matching_id,
                    InterviewSet.user_id == user_id,
                )
                .order_by(InterviewSet.created_at.desc(), InterviewSet.id.desc())
                .limit(1)
            )
        ).first()
        return InterviewLatestResponse(
            message="最近題組查詢成功",
            data=InterviewSetSummary.model_validate(row) if row is not None else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Latest interview retrieval failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail="伺服器處理失敗，請稍後再試"
        ) from None


@router.get("/{interview_set_id}", response_model=InterviewGetResponse)
@limiter.limit("100/minute")
async def get_interview_set(
    request: Request,
    interview_set_id: Annotated[int, Path(gt=0)],
    db: db_dependency,
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    """讀取已保存的題組快照，不重新查詢履歷或呼叫 AI。"""
    try:
        row = await db.scalar(
            select(InterviewSet).where(
                InterviewSet.id == interview_set_id,
                InterviewSet.user_id == user_id,
            )
        )
        # 不存在與無權讀取使用相同回應，避免透露他人的題組是否存在。
        if row is None:
            raise HTTPException(status_code=404, detail="找不到可使用的面試題組")
        return InterviewGetResponse(
            message="面試題查詢成功", data=InterviewSetRecord.model_validate(row)
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Interview retrieval failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail="伺服器處理失敗，請稍後再試"
        ) from None
