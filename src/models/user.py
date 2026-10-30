from datetime import datetime

from sqlalchemy import DateTime, Identity, String, Boolean, func, text
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class User(Base):
    __tablename__ = "users"

    # 保留 1 給舊 MVP 資料，公開註冊不能取得這個身分。
    id: Mapped[int] = mapped_column(Identity(start=2), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
