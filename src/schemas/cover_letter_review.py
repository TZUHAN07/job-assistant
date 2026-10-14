from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["title", "opening", "why_me", "why_company", "call_to_action", "full_content"]
    quote: str = Field(min_length=1, description="該欄位的逐字問題片段，不改寫。")
    category: Literal["unsupported_claim", "claim_inflation", "skill_conflation", "unsupported_outcome"]
    evidence_ids: list[str] = Field(description="相關履歷或 JD 證據 ID；沒有相關證據時可為空，不可虛構 ID。")
    reason: str = Field(min_length=1)
    suggested_revision: str = Field(min_length=1, description="保守改寫建議或建議刪除；不是已驗證事實。")


class ReviewFindings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issues: list[ReviewIssue] = Field(max_length=12)


class CoverLetterReview(BaseModel):
    status: Literal["needs_revision", "no_issues_found", "review_failed"]
    issues: list[ReviewIssue] = Field(default_factory=list)
    error: str | None = None
