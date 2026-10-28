from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.matching import Matching


class InterviewSet(Base):
    """保存一次生成的題組與當時的證據快照。"""

    __tablename__ = "interview_sets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    matching_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matchings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    matching: Mapped["Matching"] = relationship()
