from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    matching_id: int = Field(..., gt=0, description="Matching ID")
    cover_letter_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Cover Letter ID",
    )

class ApplicationListItem(BaseModel):
    id: int
    matching_id: int
    resume_id: int
    job_id: int
    cover_letter_id: Optional[int]
    status: str
    applied_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    resume_filename: str
    company: str
    job_title: str
    score: Optional[int]
    cover_letter_version: Optional[int]
    cover_letter_title: Optional[str]


class ApplicationListResponse(BaseModel):
    message: str
    data: list[ApplicationListItem]
    total: int
    limit: int
    offset: int
