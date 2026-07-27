from datetime import datetime
from typing import Optional,  TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.resume import Resume
    from src.models.job import Job
    from src.models.cover_letter import CoverLetter


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
    quick_wins: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    long_term_goals: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resume: Mapped["Resume"] = relationship(back_populates="matchings")
    job: Mapped["Job"] = relationship(back_populates="matchings")
    cover_letters: Mapped[list["CoverLetter"]] = relationship(back_populates="matching")

    def __repr__(self) -> str:
        return f"<Matching(id={self.id}, resume_id={self.resume_id}, job_id={self.job_id}, score={self.score})>"
