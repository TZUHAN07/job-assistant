from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.database import get_db
from src.models import Resume, Job, Matching, CoverLetter
from src.schemas import ResumeParsed, JobParsed, MatchingResult
from src.services.cover_letter_service import generate_cover_letter

router = APIRouter(prefix="/cover-letters", tags=["Cover Letter"])
logger = logging.getLogger(__name__)

db_dependency = Annotated[AsyncSession, Depends(get_db)]


class GenerateCoverLetterRequest(BaseModel):
    matching_id: int = Field(..., gt=0, description="Matching ID from DB")
    tone: str = Field(
        default="professional",
        description="professional / casual / formal / enthusiastic",
    )
    language: str = Field(default="zh-TW", description="zh-TW / en-US / etc")


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate(
    db: db_dependency,
    body: GenerateCoverLetterRequest,
):
    """
    Generate personalized cover letter based on Matching result.

    - Fetches matching + resume + job from DB
    - Requires matching.processed_at (LLM matching done)
    - Calls LLM cover_letter_service
    - Saves to cover_letters table (increments version if exist)
    - Returns full cover letter (title + 4 sections + full_content)
    """
    try:
        matching_result = await db.execute(
            select(Matching)
            .where(Matching.id == body.matching_id)
            .options(
                selectinload(Matching.resume),
                selectinload(Matching.job),
            )
        )
        matching_row = matching_result.scalar_one_or_none()

        if not matching_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matching {body.matching_id} not found",
            )

        if not matching_row.processed_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Matching {body.matching_id} not processed by LLM yet",
            )

        resume_row = matching_row.resume
        job_row = matching_row.job

        if not resume_row.parsed_data or not job_row.parsed_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume/Job parsed_data missing",
            )

        resume_parsed = ResumeParsed(**resume_row.parsed_data)
        job_parsed = JobParsed(**job_row.parsed_data)
        matching_data = MatchingResult(
            match_reasons=matching_row.match_reasons or [],
            matched_skills=matching_row.matched_skills or [],
            missing_skills=matching_row.missing_skills or [],
            quick_wins=matching_row.quick_wins or [],
            long_term_goals=matching_row.long_term_goals or [],
            score=matching_row.score or 0,
        )

        max_version_result = await db.execute(
            select(func.coalesce(func.max(CoverLetter.version), 0)).where(
                CoverLetter.matching_id == body.matching_id
            )
        )
        next_version = max_version_result.scalar() + 1

        logger.info(
            f"Generating cover letter: matching_id={body.matching_id}, "
            f"version={next_version}, tone={body.tone}, language={body.language}"
        )

        letter_result = await generate_cover_letter(
            resume=resume_parsed,
            job=job_parsed,
            matching=matching_data,
            tone=body.tone,
            language=body.language,
        )

        if letter_result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM 生成求職信失敗, 請稍後再試",
            )

        logger.info(f"Cover letter generated: title={letter_result.title!r}")

        new_letter = CoverLetter(
            matching_id=body.matching_id,
            title=letter_result.title,
            content=letter_result.full_content,
            version=next_version,
            tone=body.tone,
            language=body.language,
        )
        db.add(new_letter)
        await db.commit()
        await db.refresh(new_letter)

        logger.info(f"Cover letter {new_letter.id} saved (v{new_letter.version})")

        return {
            "message": "求職信生成成功",
            "data": {
                "id": new_letter.id,
                "matching_id": new_letter.matching_id,
                "title": new_letter.title,
                "content": new_letter.content,
                "version": new_letter.version,
                "tone": new_letter.tone,
                "language": new_letter.language,
                "is_favorite": new_letter.is_favorite,
                "created_at": new_letter.created_at,
                "sections": {
                    "opening": letter_result.opening,
                    "why_me": letter_result.why_me,
                    "why_company": letter_result.why_company,
                    "call_to_action": letter_result.call_to_action,
                },
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error during cover letter generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理失敗: {str(e)}",
        )
