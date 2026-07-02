from io import BytesIO
from typing import Annotated

from fastapi import File, UploadFile, APIRouter, Depends, HTTPException
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.database import get_db
from src.models.resume import Resume


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

        reader = PdfReader(BytesIO(file_bytes))
        content_text = ""
        for page in reader.pages:
            content_text += page.extract_text() or ""

        new_resume = Resume(
            filename=filename,
            file_size=file_size,
            content_text=content_text,
        )

        db.add(new_resume)
        await db.commit()
        await db.refresh(new_resume)

        return {
            "message": "履歷上傳並解析成功",
            "data": {
                "id": new_resume.id,
                "filename": new_resume.filename,
                "file_size": new_resume.file_size,
                "uploaded_at": new_resume.uploaded_at,
                "extracted_text": (content_text[:200] + "...")
                if len(content_text) > 200
                else content_text,
                "processed_at": None,
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"檔案處理失敗: {str(e)}",
        )
