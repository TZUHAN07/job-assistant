from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Matching(Base):
    __tablename__ = "matchings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[ Optional[int]] = mapped_column(Integer, nullable=True)
    match_reasons: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    matched_skills: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    recommendations: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Matching(id={self.id}, resume_id={self.resume_id}, job_id={self.job_id}, score={self.score})>"
