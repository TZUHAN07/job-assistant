from typing import Optional

from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    matching_id: int = Field(..., gt=0, description="Matching ID")
    cover_letter_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Cover Letter ID",
    )