from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.database import get_db
from src.limiter import limiter
from src.models import Resume, Job, Matching
from src.schemas import ResumeParsed, JobParsed
from src.services.matching_service import calculate_matching_score
from src.utils.time_utils import utc_now

router = APIRouter(prefix="/matchings", tags=["Matching"])
logger = logging.getLogger(__name__)

db_dependency = Annotated[AsyncSession, Depends(get_db)]


class MatchingScoreRequest(BaseModel):
    resume_id: int = Field(..., gt=0, description="Resume ID from DB")
    job_id: int = Field(..., gt=0, description="Job ID from DB")


@router.post("/score", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def calculate_score(
    request: Request,
    db: db_dependency,
    body: MatchingScoreRequest,
):
    """
    Calculate matching score for a Resume × Job pair.

    - Fetches resume + job from DB by ID
    - Requires resume.parsed_data + job.parsed_data (LLM extracted)
    - Calls LLM matching_service
    - Saves to matchings table (partial save on LLM fail)
    - Returns full matching result
    """

    try:
        resume_result = await db.execute(
            select(Resume).where(Resume.id == body.resume_id)
        )
        resume_row = resume_result.scalar_one_or_none()

        if not resume_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {body.resume_id} not found",
            )

        if not resume_row.parsed_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resume {body.resume_id} has no parsed_data (LLM 尚未處理)",
            )

        job_result = await db.execute(select(Job).where(Job.id == body.job_id))
        job_row = job_result.scalar_one_or_none()

        if not job_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {body.job_id} not found",
            )

        if not job_row.parsed_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {body.job_id} has no parsed_data (LLM 尚未處理)",
            )

        resume_parsed = ResumeParsed(**resume_row.parsed_data)
        job_parsed = JobParsed(**job_row.parsed_data)

        logger.info(f"Calculating matching: resume={body.resume_id}, job={body.job_id}")

        matching_result = await calculate_matching_score(resume_parsed, job_parsed)

        if matching_result:
            logger.info(
                f"Matching scored: score={matching_result.score}, "
                f"matched={len(matching_result.matched_skills)}"
            )
        else:
            logger.warning(
                f"LLM matching failed (partial save): {body.resume_id} × {body.job_id}"
            )

        matching_data = matching_result.model_dump() if matching_result else {}
        processed_at = utc_now() if matching_result else None

        new_matching = Matching(
            resume_id=body.resume_id,
            job_id=body.job_id,
            **matching_data,
            processed_at=processed_at,
        )
        db.add(new_matching)
        await db.commit()
        await db.refresh(new_matching)

        logger.info(f"Matching {new_matching.id} saved")

        message = (
            "匹配評分成功" if matching_result else "資料已保存, LLM 評分失敗待重試"
        )

        return {
            "message": message,
            "data": {
                "id": new_matching.id,
                "resume_id": new_matching.resume_id,
                "job_id": new_matching.job_id,
                "score": new_matching.score,
                "match_reasons": new_matching.match_reasons,
                "matched_skills": new_matching.matched_skills,
                "missing_skills": new_matching.missing_skills,
                "quick_wins": new_matching.quick_wins,
                "long_term_goals": new_matching.long_term_goals,
                "processed_at": new_matching.processed_at,
                "created_at": new_matching.created_at,
            },
        }

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during matching calculation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )


@router.get("/{matching_id}", status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def get_matching(
    request: Request,
    db: db_dependency,
    matching_id: int = Path(..., gt=0, title="Matching ID"),
):
    """
    Retrieve a Matching record by ID.

    - Returns the matching data if found
    - Raises 404 if not found
    """

    try:
        matching_result = await db.execute(
            select(Matching)
            .where(Matching.id == matching_id)
            .options(selectinload(Matching.resume), selectinload(Matching.job))
        )
        matching_row = matching_result.scalar_one_or_none()

        if not matching_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matching {matching_id} not found",
            )

        resume_parsed = matching_row.resume.parsed_data or {}
        job_parsed = matching_row.job.parsed_data or {}

        return {
            "message": "查詢成功",
            "data": {
                "id": matching_row.id,
                "resume_id": matching_row.resume_id,
                "job_id": matching_row.job_id,
                "score": matching_row.score,
                "match_reasons": matching_row.match_reasons,
                "matched_skills": matching_row.matched_skills,
                "missing_skills": matching_row.missing_skills,
                "quick_wins": matching_row.quick_wins,
                "long_term_goals": matching_row.long_term_goals,
                "processed_at": matching_row.processed_at,
                "created_at": matching_row.created_at,
                "resume_name": resume_parsed.get("name")
                or matching_row.resume.filename,
                "job_title": job_parsed.get("title") or "未命名職缺",
                "job_company": job_parsed.get("company") or "",
            },
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception("Unexpected error during matching retrieval")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )


@router.delete("/{matching_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/hour")
async def delete_matching(
    request: Request,
    db: db_dependency,
    matching_id: int = Path(..., gt=0, title="Matching ID"),
):
    """
    Delete a Matching record by ID.

    - FK CASCADE 自動連帶刪 cover_letters
    - Raises 404 if not found
    - Returns 204 No Content on successful deletion
    """

    try:
        matching_result = await db.execute(
            select(Matching).where(Matching.id == matching_id)
        )
        matching_row = matching_result.scalar_one_or_none()

        if not matching_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matching {matching_id} not found",
            )

        await db.delete(matching_row)
        await db.commit()

        logger.info(f"Matching {matching_id} deleted (with cascade cover_letters)")

        return None

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during matching deletion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )
