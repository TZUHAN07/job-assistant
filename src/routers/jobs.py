from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.models.job import Job
from src.services.jd_service import extract_from_url, extract_from_text
from src.utils.time_utils import utc_now

router = APIRouter(prefix="/jobs", tags=["Job"])
logger = logging.getLogger(__name__)

db_dependency = Annotated[AsyncSession, Depends(get_db)]

class ParseUrlRequest(BaseModel):
     url: str = Field(..., pattern=r"^https?://.+", description="JD URL to scrape")

class ParseTextRequest(BaseModel):
     text: str = Field(..., min_length=50, description="Pasted JD content")



@router.post("/parse-url", status_code=status.HTTP_201_CREATED)
async def parse_jd_from_url(
    db: db_dependency,
    body: ParseUrlRequest,
):
    """Scrape JD URL via Firecrawl → LLM extract → save to DB."""

    try:
        raw_content, jd_result = await extract_from_url(body.url)

        if raw_content is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無法解析此 URL, 請改用 paste text 模式",
            )

        parsed_data = jd_result.model_dump() if jd_result else None
        processed_at = utc_now() if jd_result else None

        if jd_result:
            logger.info(f"JD extracted: title={jd_result.title!r}, company={jd_result.company!r}")
        else:
            logger.warning(f"LLM extraction failed (partial save): {body.url}")

        new_job = Job(
            source_type="url_scrape",
            source_url=body.url,
            raw_content=raw_content,
            parsed_data=parsed_data,
            processed_at=processed_at,
        )
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)

        logger.info(f"Job {new_job.id} saved")

        message = (
            "JD 解析成功" if jd_result
            else "JD 抓取成功, LLM 解析失敗待重試"
        )

        return {
            "message": message,
            "data": {
                "id": new_job.id,
                "source_type": new_job.source_type,
                "source_url": new_job.source_url,
                "parsed_data": new_job.parsed_data,
                "processed_at": new_job.processed_at,
                "created_at": new_job.created_at,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error during JD URL parsing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理失敗: {str(e)}",
        )
    

@router.post("/parse-text", status_code=status.HTTP_201_CREATED)
async def parse_jd_from_text(
    db: db_dependency,
    body: ParseTextRequest,
):
    """Direct text → LLM extract → save to DB (works with any platform, safer for anti-bot)."""
    try:
        jd_result = await extract_from_text(body.text)

        parsed_data = jd_result.model_dump() if jd_result else None
        processed_at = utc_now() if jd_result else None

        if jd_result:
            logger.info(f"JD extracted: title={jd_result.title!r}, company={jd_result.company!r}")
        else:
            logger.warning("LLM extraction failed (partial save)")

        new_job = Job(
            source_type="text_paste",
            source_url=None,          
            raw_content=body.text,   
            parsed_data=parsed_data,
            processed_at=processed_at,
        )
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)

        logger.info(f"Job {new_job.id} saved")

        message = (
            "JD 解析成功" if jd_result
            else "上傳成功, LLM 解析失敗待重試"
        )

        return {
            "message": message,
            "data": {
                "id": new_job.id,
                "source_type": new_job.source_type,
                "source_url": new_job.source_url,
                "parsed_data": new_job.parsed_data,
                "processed_at": new_job.processed_at,
                "created_at": new_job.created_at,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error during JD text parsing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理失敗: {str(e)}",
        )