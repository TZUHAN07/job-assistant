from typing import Annotated
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Path
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.services.auth_service import CurrentUserId, get_current_user_id
from src.services.data_access import matching_owned_by, letter_owned_by
from src.database import get_db
from src.limiter import limiter
from src.models import Resume, Job, Matching, CoverLetter, CoverLetterTemplate
from src.services.cover_letter_template_service import generate_from_template, resume_fingerprint, template_snapshot
from src.schemas.cover_letter_edit import CoverLetterEditRequest
from src.schemas import ResumeParsed, JobParsed, MatchingResult
from src.services.cover_letter_workflow import generate_reviewed_letter

router = APIRouter(prefix="/cover-letters", tags=["Cover Letter"], dependencies=[Depends(get_current_user_id)])
logger = logging.getLogger(__name__)

db_dependency = Annotated[AsyncSession, Depends(get_db)]


class GenerateCoverLetterRequest(BaseModel):
    matching_id: int = Field(..., gt=0, description="Matching ID from DB")
    template_id: int | None = Field(default=None, gt=0)
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
    user_id: CurrentUserId,
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
            .where(Matching.id == body.matching_id, matching_owned_by(user_id))
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

        if body.template_id is not None:
            template = await db.scalar(select(CoverLetterTemplate).where(
                CoverLetterTemplate.id == body.template_id,
                CoverLetterTemplate.user_id == user_id,
                CoverLetterTemplate.resume_id == resume_row.id))
            if template is None:
                raise HTTPException(404, "Template not found")
            if template.resume_hash != resume_fingerprint(resume_row):
                raise HTTPException(409, "履歷已變更，請重新確認並儲存底稿")
            if template.language != body.language:
                raise HTTPException(409, "請使用與底稿相同的語言")
            letter_result, review_metadata = await generate_from_template(
                resume_parsed, job_parsed, template_snapshot(template))
        else:
            letter_result, review_metadata = await generate_reviewed_letter(
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

        locked_matching = await db.scalar(select(Matching.id).where(
            Matching.id == body.matching_id, matching_owned_by(user_id),
        ).with_for_update())
        if locked_matching is None:
            raise HTTPException(404, "Matching not found")
        max_version = await db.scalar(select(func.max(CoverLetter.version)).where(
            CoverLetter.matching_id == body.matching_id, CoverLetter.user_id == user_id,
        ))
        next_version = (max_version or 0) + 1

        new_letter = CoverLetter(
            user_id=user_id,
            matching_id=body.matching_id,
            title=letter_result.title,
            content=letter_result.full_content,
            opening=letter_result.opening,
            why_me=letter_result.why_me,
            why_company=letter_result.why_company,
            call_to_action=letter_result.call_to_action,
            review_metadata=review_metadata,
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
                "review_metadata": new_letter.review_metadata,
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
    user_id: CurrentUserId,
    matching_id: int = Query(..., gt=0, description="Matching ID to filter"),
):
    """
    List all cover letter versions for a given matching.

    - Returns list ordered by version desc (newest first)
    - Empty list if no letters yet (not 404)
    """
    matching = await db.scalar(select(Matching.id).where(
        Matching.id == matching_id, matching_owned_by(user_id),
    ))
    if matching is None:
        raise HTTPException(404, "Matching not found")
    result = await db.execute(
        select(CoverLetter)
        .where(CoverLetter.matching_id == matching_id, letter_owned_by(user_id))
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
                "review_metadata": letter.review_metadata,
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
    user_id: CurrentUserId,
):
    """保存人工修改為新版本，保留原信件及 Application 的選用關係。"""
    try:
        source = await db.scalar(select(CoverLetter).where(
            CoverLetter.id == letter_id, letter_owned_by(user_id),
        ))
        if source is None:
            raise HTTPException(404, "Cover letter not found")
        locked_matching = await db.scalar(select(Matching.id).where(
            Matching.id == source.matching_id, matching_owned_by(user_id),
        ).with_for_update())
        if locked_matching is None:
            raise HTTPException(404, "Matching not found")
        sections = body.sections.model_dump() if body.sections else {}
        content = "\n\n".join(sections.values()) if sections else body.content
        max_version = await db.scalar(select(func.max(CoverLetter.version)).where(
            CoverLetter.matching_id == source.matching_id, CoverLetter.user_id == user_id,
        ))
        letter = CoverLetter(
            user_id=user_id, matching_id=source.matching_id,
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
                "review_metadata": letter.review_metadata,
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
