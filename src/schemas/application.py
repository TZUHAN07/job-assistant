from datetime import datetime
from typing import Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"status": "applied", "notes": "已寄出求職信"}]},
    )
    status: Optional[Literal["preparing", "applied", "interview", "closed"]] = None
    applied_at: Optional[AwareDatetime] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一個要更新的欄位")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status 不可為 null")
        return self


class ApplicationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    matching_id: int
    resume_id: int
    job_id: int
    cover_letter_id: Optional[int]
    status: str
    applied_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ApplicationUpdateResponse(BaseModel):
    message: str
    data: ApplicationRecord
