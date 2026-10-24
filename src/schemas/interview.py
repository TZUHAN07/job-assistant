from typing import Literal

from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    question: str = Field(min_length=1)
    kind: Literal["project_experience", "hypothetical"]
    rationale: str = Field(min_length=1)
    job_evidence_ids: list[str] = Field(min_length=1)
    resume_evidence_ids: list[str]


class InterviewQuestionSet(BaseModel):
    questions: list[InterviewQuestion] = Field(min_length=5, max_length=5)
