from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="count")

    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_perishable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=True
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class InventoryChangeLog(Base):
    __tablename__ = "inventory_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inventory_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("inventory_items.id", ondelete="SET NULL"), index=True, nullable=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("detection_sessions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    proposal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("detection_proposals.id", ondelete="SET NULL"), index=True, nullable=True
    )
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
