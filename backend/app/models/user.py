from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base
from .enums import UserRole


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, index=True, autoincrement=False
    )
    username: Mapped[str | None] = mapped_column(String(255), index=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    auth_date: Mapped[datetime | None] = mapped_column(default=None)

    tasks = relationship("ParsingTask", back_populates="user", cascade="all, delete")
    files = relationship("UploadedFile", back_populates="user", cascade="all, delete")
    mappings = relationship(
        "ProductMapping", back_populates="user", cascade="all, delete"
    )

