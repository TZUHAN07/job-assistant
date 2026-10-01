import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.limiter import limiter
from src.models import Application, CoverLetter, Matching
from src.schemas.application import ApplicationCreate

router = APIRouter(prefix="/applications", tags=["Application"])
logger = logging.getLogger(__name__)

db_dependency = Annotated[AsyncSession, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
async def create_application(
    request: Request,
    db: db_dependency,
    body: ApplicationCreate,
):
    """
    Create an Application from an existing Matching.

    - Requires a valid Matching
    - Uses Matching's resume_id and job_id
    - Optionally associates a Cover Letter
    - Creates the Application with status='preparing'
    """

    try:
        matching_result = await db.execute(
            select(Matching).where(Matching.id == body.matching_id)
        )
        matching_row = matching_result.scalar_one_or_none()

        if not matching_row:
            raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Matching {body.matching_id} not found",
                )

        if body.cover_letter_id is not None:
            cl_result = await db.execute(
                select(CoverLetter).where(
                    CoverLetter.id == body.cover_letter_id,
                    CoverLetter.matching_id == body.matching_id,
                )
            )
            cover_letter_row = cl_result.scalar_one_or_none()

            if not cover_letter_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                            f"Cover letter {body.cover_letter_id}"
                            f"not found for this matching"),
                )

        new_application = Application(
            user_id=1,
            matching_id=matching_row.id,
            resume_id=matching_row.resume_id,
            job_id=matching_row.job_id,
            cover_letter_id=body.cover_letter_id,
        )

        db.add(new_application)
        await db.commit()
        await db.refresh(new_application)

        logger.info(
            f"Application {new_application.id} created: "
            f"matching={new_application.matching_id}, "
            f"resume={new_application.resume_id}, "
            f"job={new_application.job_id}"
        )

        return {
            "message": "求職追蹤建立成功",
            "data": {
                "id": new_application.id,
                "user_id": new_application.user_id,
                "matching_id": new_application.matching_id,
                "resume_id": new_application.resume_id,
                "job_id": new_application.job_id,
                "cover_letter_id": new_application.cover_letter_id,
                "status": new_application.status,
                "applied_at": new_application.applied_at,
                "notes": new_application.notes,
                "created_at": new_application.created_at,
                "updated_at": new_application.updated_at,
            },
        }

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during application creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )
