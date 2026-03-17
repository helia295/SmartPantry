from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(nullable=True)
    prep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cook_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    servings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cuisine: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    dietary_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    nutrition_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    instructions_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_raw: Mapped[str] = mapped_column(Text, nullable=False)
    ingredient_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity_text: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
