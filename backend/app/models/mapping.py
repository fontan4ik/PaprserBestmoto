import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ProductMapping(Base):
    __tablename__ = "product_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_product_id: Mapped[str] = mapped_column(String(255), index=True)
    matched_product_id: Mapped[str | None] = mapped_column(String(255), index=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime]

    user = relationship("User", back_populates="mappings")

