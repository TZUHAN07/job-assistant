from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InterviewQuestion(BaseModel):
    question: str = Field(min_length=1)
    kind: Literal["project_experience", "hypothetical"]
    rationale: str = Field(min_length=1)
    job_evidence_ids: list[str] = Field(min_length=1)
    resume_evidence_ids: list[str]


class InterviewQuestionSet(BaseModel):
    questions: list[InterviewQuestion] = Field(min_length=5, max_length=5)


class InterviewGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matching_id: int = Field(gt=0, strict=True, description="要準備面試的匹配紀錄 ID")


class InterviewQuestionWithEvidence(InterviewQuestion):
    job_evidence: list[dict[str, str]]
    resume_evidence: list[dict[str, str]]


class InterviewReport(BaseModel):
    schema_version: Literal[1]
    matching_id: int = Field(gt=0)
    created_at: datetime
    model: str
    model_rounds: int = Field(ge=1, le=3)
    tool_calls: int = Field(ge=0, le=6)
    validation: str
    sources: dict[str, Any]
    evidence_catalog: dict[str, Any]
    questions: list[InterviewQuestionWithEvidence] = Field(min_length=5, max_length=5)


class InterviewSetRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    matching_id: int
    created_at: datetime
    report: InterviewReport


class InterviewGenerateResponse(BaseModel):
    message: str
    data: InterviewSetRecord
