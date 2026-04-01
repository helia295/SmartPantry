"""add recipe embeddings

Revision ID: 0002_add_recipe_embeddings
Revises: 0001_initial_schema
Create Date: 2026-03-31 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_recipe_embeddings"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            """
            CREATE TABLE recipe_embeddings (
                id SERIAL PRIMARY KEY,
                recipe_id INTEGER NOT NULL UNIQUE REFERENCES recipes(id) ON DELETE CASCADE,
                document_type VARCHAR(32) NOT NULL,
                document_text TEXT NOT NULL,
                title_snapshot VARCHAR(255) NOT NULL,
                total_minutes_snapshot INTEGER NULL,
                embedding vector(1536) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        op.execute("CREATE INDEX ix_recipe_embeddings_recipe_id ON recipe_embeddings (recipe_id)")
    else:
        op.create_table(
            "recipe_embeddings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(length=32), nullable=False),
            sa.Column("document_text", sa.Text(), nullable=False),
            sa.Column("title_snapshot", sa.String(length=255), nullable=False),
            sa.Column("total_minutes_snapshot", sa.Integer(), nullable=True),
            sa.Column("embedding", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("recipe_id", name="uq_recipe_embeddings_recipe_id"),
        )
        op.create_index("ix_recipe_embeddings_recipe_id", "recipe_embeddings", ["recipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipe_embeddings_recipe_id", table_name="recipe_embeddings")
    op.drop_table("recipe_embeddings")
