from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.matching import Matching


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
    opening: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_me: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    matching: Mapped["Matching"] = relationship(back_populates="cover_letters")



    def __repr__(self) -> str:
        return f"<CoverLetter(id={self.id}, matching_id={self.matching_id}, version={self.version}, title={self.title!r})>"
