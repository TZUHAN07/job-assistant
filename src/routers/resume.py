from io import BytesIO
from typing import Annotated

from fastapi import File, UploadFile, APIRouter, Depends, HTTPException, Path, Request
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.limiter import limiter
from src.models.resume import Resume
from src.services.llm_service import extract_resume_structured
from src.utils.time_utils import utc_now

import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/resumes", tags=["Resume"])

db_dependency = Annotated[AsyncSession, Depends(get_db)]

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@router.post("/upload", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def upload_resume(
    request: Request,
    db: db_dependency,
    file: UploadFile = File(...),
):

    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="僅支援上傳 PDF 格式的檔案",
        )

    try:
        file_bytes = await file.read()
        filename = file.filename
        file_size = len(file_bytes)

        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"檔案過大, 上限 {MAX_UPLOAD_SIZE // 1024 // 1024}MB",
            )

        logger.info(f"Upload received: {filename} ({file_size} bytes)")

        reader = PdfReader(BytesIO(file_bytes))
        content_text = ""
        for page in reader.pages:
            content_text += page.extract_text() or ""

        llm_result = await extract_resume_structured(content_text)

        if llm_result:
            logger.info(
                f"Resume extracted: name={llm_result.name!r}, skills={len(llm_result.skills)}"
            )
        else:
            logger.warning(f"LLM extraction failed (partial save): {filename}")

        parsed_data = llm_result.model_dump() if llm_result else None
        processed_at = utc_now() if llm_result else None

        new_resume = Resume(
            filename=filename,
            file_size=file_size,
            content_text=content_text,
            parsed_data=parsed_data,
            processed_at=processed_at,
        )

        db.add(new_resume)
        await db.commit()
        await db.refresh(new_resume)

        logger.info(f"Resume {new_resume.id} saved")

        message = (
            "履歷上傳並解析成功" if llm_result else "履歷上傳成功, LLM 解析失敗待重試"
        )

        return {
            "message": message,
            "data": {
                "id": new_resume.id,
                "filename": new_resume.filename,
                "file_size": new_resume.file_size,
                "uploaded_at": new_resume.uploaded_at,
                "extracted_text": (
                    content_text[:200] + "..."
                    if len(content_text) > 200
                    else content_text
                ),
                "processed_at": new_resume.processed_at,
                "parsed_data": new_resume.parsed_data,
            },
        }

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during resume upload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )


@router.get("", status_code=status.HTTP_200_OK)
@limiter.limit("100/minute")
async def list_resumes(request: Request, db: db_dependency):
    result = await db.execute(
        select(Resume).order_by(Resume.uploaded_at.desc()).limit(20)
    )

    resumes = result.scalars().all()

    return {
        "message": "查詢成功",
        "data": [
            {
                "id": resume.id,
                "filename": resume.filename,
                "uploaded_at": resume.uploaded_at,
                "processed_at": resume.processed_at,
                "resume_name": (resume.parsed_data or {}).get("name")
                or resume.filename,
            }
            for resume in resumes
        ],
    }


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
async def delete_resume(
    request: Request,
    db: db_dependency,
    resume_id: int = Path(..., gt=0, title="Resume ID"),
):
    """
    Delete a resume by its ID.

    - FK CASCADE 自動連帶刪 matchings + cover_letters (三層 cascade)
    - Raises 404 if not found
    - Returns 204 No Content on successful deletion
    """

    try:
        resume_result = await db.execute(select(Resume).where(Resume.id == resume_id))
        resume_row = resume_result.scalar_one_or_none()

        if not resume_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {resume_id} not found",
            )

        await db.delete(resume_row)
        await db.commit()

        logger.info(
            f"Resume {resume_id} deleted (with cascade matchings + cover_letters)"
        )
        return None

    except HTTPException:
        raise

    except Exception:
        await db.rollback()
        logger.exception("Unexpected error during resume deletion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="伺服器處理失敗, 請稍後再試",
        )
