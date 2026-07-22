from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class CoverLetter(Base):
    """Cover letter generated from a specific Matching."""

    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    matching_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matchings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tone: Mapped[str] = mapped_column(
        String(20), default="professional", nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="zh-TW", nullable=False)

    is_favorite: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CoverLetter(id={self.id}, matching_id={self.matching_id}, version={self.version}, title={self.title!r})>"
