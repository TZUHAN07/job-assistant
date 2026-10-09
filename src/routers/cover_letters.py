from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Path
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.database import get_db
from src.limiter import limiter
from src.models import Resume, Job, Matching, CoverLetter
from src.schemas.cover_letter_edit import CoverLetterEditRequest
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
@limiter.limit("20/hour")
async def generate(
    request: Request,
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

        await db.execute(select(Matching).where(
            Matching.id == body.matching_id,
        ).with_for_update())
        max_version = await db.scalar(select(func.max(CoverLetter.version)).where(
            CoverLetter.matching_id == body.matching_id,
        ))
        next_version = (max_version or 0) + 1

        new_letter = CoverLetter(
            matching_id=body.matching_id,
            title=letter_result.title,
            content=letter_result.full_content,
            opening=letter_result.opening,
            why_me=letter_result.why_me,
            why_company=letter_result.why_company,
            call_to_action=letter_result.call_to_action,
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

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during cover letter generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )


@router.get("", status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def list_by_matching(
    request: Request,
    db: db_dependency,
    matching_id: int = Query(..., gt=0, description="Matching ID to filter"),
):
    """
    List all cover letter versions for a given matching.

    - Returns list ordered by version desc (newest first)
    - Empty list if no letters yet (not 404)
    """
    result = await db.execute(
        select(CoverLetter)
        .where(CoverLetter.matching_id == matching_id)
        .order_by(CoverLetter.version.desc())
    )
    letters = result.scalars().all()

    return {
        "message": "查詢成功",
        "data": [
            {
                "id": letter.id,
                "matching_id": letter.matching_id,
                "title": letter.title,
                "content": letter.content,
                "version": letter.version,
                "tone": letter.tone,
                "language": letter.language,
                "is_favorite": letter.is_favorite,
                "created_at": letter.created_at,
                "sections": {
                    "opening": letter.opening,
                    "why_me": letter.why_me,
                    "why_company": letter.why_company,
                    "call_to_action": letter.call_to_action,
                },
            }
            for letter in letters
        ],
    }


@router.post("/{letter_id}/versions", status_code=status.HTTP_201_CREATED)
async def save_edited_version(
    letter_id: Annotated[int, Path(gt=0)],
    body: CoverLetterEditRequest,
    db: db_dependency,
):
    """保存人工修改為新版本，保留原信件及 Application 的選用關係。"""
    try:
        source = await db.scalar(select(CoverLetter).where(
            CoverLetter.id == letter_id, CoverLetter.user_id == 1,
        ))
        if source is None:
            raise HTTPException(404, "Cover letter not found")
        await db.execute(select(Matching).where(
            Matching.id == source.matching_id,
        ).with_for_update())
        sections = body.sections.model_dump() if body.sections else {}
        content = "\n\n".join(sections.values()) if sections else body.content
        max_version = await db.scalar(select(func.max(CoverLetter.version)).where(
            CoverLetter.matching_id == source.matching_id,
        ))
        letter = CoverLetter(
            user_id=source.user_id, matching_id=source.matching_id,
            title=source.title, tone=source.tone, language=source.language,
            version=(max_version or 0) + 1, content=content, **sections,
        )
        db.add(letter)
        await db.commit()
        await db.refresh(letter)
        return {"message": "已儲存為新版本", "data": {
            "id": letter.id, "matching_id": letter.matching_id,
            "title": letter.title, "content": letter.content,
            "version": letter.version, "tone": letter.tone,
            "language": letter.language, "is_favorite": letter.is_favorite,
            "created_at": letter.created_at,
            "sections": {key: getattr(letter, key) for key in (
                "opening", "why_me", "why_company", "call_to_action",
            )},
        }}
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Failed to save edited cover letter")
        raise HTTPException(500, "儲存失敗，請稍後再試")
