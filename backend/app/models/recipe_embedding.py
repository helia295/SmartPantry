from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator

from app.db import Base


class EmbeddingVectorType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())


class RecipeEmbedding(Base):
    __tablename__ = "recipe_embeddings"
    __table_args__ = (
        UniqueConstraint("recipe_id", name="uq_recipe_embeddings_recipe_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False, default="recipe")
    document_text: Mapped[str] = mapped_column(Text, nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    total_minutes_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVectorType(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
