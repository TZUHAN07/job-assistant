from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.database import get_db
from src.models import Matching, CoverLetterTemplate
from src.services.auth_service import CurrentUserId
from src.services.data_access import matching_owned_by
from src.schemas.cover_letter_template import TemplateCreate
from src.services.cover_letter_template_service import resume_fingerprint, template_snapshot

router = APIRouter(prefix="/cover-letter-templates", tags=["Cover Letter Templates"])
DB = Annotated[AsyncSession, Depends(get_db)]


async def owned_resume(db, matching_id, user_id):
    matching = await db.scalar(select(Matching).where(Matching.id == matching_id,
        matching_owned_by(user_id)).options(selectinload(Matching.resume)))
    if matching is None:
        raise HTTPException(404, "Matching not found")
    if not matching.resume.parsed_data:
        raise HTTPException(409, "履歷尚未解析")
    return matching.resume


@router.get("")
async def list_templates(db: DB, user_id: CurrentUserId, matching_id: Annotated[int, Query(gt=0)]):
    resume = await owned_resume(db, matching_id, user_id)
    rows = (await db.scalars(select(CoverLetterTemplate).where(
        CoverLetterTemplate.user_id == user_id, CoverLetterTemplate.resume_id == resume.id)
        .order_by(CoverLetterTemplate.id.desc()))).all()
    fingerprint = resume_fingerprint(resume)
    return {"data": [{**template_snapshot(row), "stale": row.resume_hash != fingerprint} for row in rows]}


@router.post("", status_code=201)
async def create_template(body: TemplateCreate, db: DB, user_id: CurrentUserId):
    resume = await owned_resume(db, body.matching_id, user_id)
    row = CoverLetterTemplate(user_id=user_id, resume_id=resume.id,
        resume_hash=resume_fingerprint(resume), **body.model_dump(exclude={"matching_id"}))
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except Exception:
        await db.rollback()
        raise
    return {"message": "底稿已儲存；修改後再次儲存會建立新底稿，不影響舊求職信。", "data": template_snapshot(row)}
