from io import BytesIO
from typing import Annotated

from fastapi import File, UploadFile, APIRouter, Depends, HTTPException
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.models.resume import Resume
from src.services.llm_service import extract_resume_structured
from src.utils.time_utils import utc_now

import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/resumes", tags=["Resume"])

db_dependency = Annotated[AsyncSession, Depends(get_db)]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
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

    except Exception as e:
        await db.rollback()
        logger.exception(f"Unexpected error during resume upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"檔案處理失敗: {str(e)}",
        )
