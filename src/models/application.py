from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.resume import Resume
    from src.models.job import Job
    from src.models.matching import Matching
    from src.models.cover_letter import CoverLetter

class Application(Base):
    """求職申請追蹤，記錄當時使用的履歷、職缺、匹配結果與求職信版本。"""

    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)

    matching_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matchings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cover_letter_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cover_letters.id", ondelete="SET NULL"),
        nullable=True, 
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="preparing",
        nullable=False,
        index=True,
        comment="preparing | applied | interview | closed",
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,  
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    matching: Mapped["Matching"] = relationship()
    resume: Mapped["Resume"] = relationship()
    job: Mapped["Job"] = relationship()
    cover_letter: Mapped[Optional["CoverLetter"]] = relationship()

    def __repr__(self) -> str:
        return (
            f"<Application(id={self.id}, job_id={self.job_id}, "
            f"resume_id={self.resume_id}, status={self.status!r})>"
        )