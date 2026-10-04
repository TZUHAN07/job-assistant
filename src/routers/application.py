import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.limiter import limiter
from src.models import Application, CoverLetter, Matching
from src.schemas.application import (
    ApplicationCreate, ApplicationListResponse, ApplicationUpdate,
    ApplicationRecord, ApplicationUpdateResponse,
)

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


@router.get("", response_model=ApplicationListResponse)
@limiter.limit("100/minute")
async def list_applications(
    request: Request,
    db: db_dependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List tracking records with their selected cover letter version, newest first."""
    try:
        owner = Application.user_id == 1
        total = await db.scalar(select(func.count(Application.id)).where(owner))
        result = await db.execute(
            select(Application)
            .where(owner)
            .options(
                selectinload(Application.resume),
                selectinload(Application.job),
                selectinload(Application.matching),
                selectinload(Application.cover_letter),
            )
            .order_by(Application.created_at.desc(), Application.id.desc())
            .limit(limit)
            .offset(offset)
        )
        data = []
        for row in result.scalars():
            job_data = row.job.parsed_data or {}
            letter = row.cover_letter
            data.append({
                "id": row.id,
                "matching_id": row.matching_id,
                "resume_id": row.resume_id,
                "job_id": row.job_id,
                "cover_letter_id": row.cover_letter_id,
                "status": row.status,
                "applied_at": row.applied_at,
                "notes": row.notes,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "resume_filename": row.resume.filename,
                "company": job_data.get("company") or "",
                "job_title": job_data.get("title") or "",
                "score": row.matching.score,
                "cover_letter_version": letter.version if letter else None,
                "cover_letter_title": letter.title if letter else None,
            })
        return {"message": "查詢成功", "data": data, "total": total,
                "limit": limit, "offset": offset}
    except Exception:
        logger.exception("Unexpected error during application listing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )


@router.patch("/{application_id}", response_model=ApplicationUpdateResponse)
@limiter.limit("30/hour")
async def update_application(
    request: Request,
    db: db_dependency,
    application_id: Annotated[int, Path(gt=0)],
    body: ApplicationUpdate,
):
    """更新狀態、投遞時間與備註。未傳欄位保留；時間與備註可用 null 清空。

    狀態不會自動改寫投遞時間；applied_at 需提供含時區的時間。
    """
    try:
        result = await db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.user_id == 1,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="求職紀錄不存在")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return {"message": "求職追蹤更新成功", "data": ApplicationRecord.model_validate(row)}
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during application update")
        raise HTTPException(status_code=500, detail="伺服器處理失敗, 請稍後再試")


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/hour")
async def delete_application(
    request: Request,
    db: db_dependency,
    application_id: Annotated[int, Path(gt=0)],
):
    """刪除求職追蹤紀錄，保留履歷、職缺、匹配結果與求職信。"""
    try:
        result = await db.execute(
            select(Application).where(
                Application.id == application_id,
                Application.user_id == 1,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="求職紀錄不存在")

        await db.delete(row)
        await db.commit()

        logger.info(f"Application {application_id} deleted")
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during application deletion")
        raise HTTPException(status_code=500, detail="伺服器處理失敗, 請稍後再試")
