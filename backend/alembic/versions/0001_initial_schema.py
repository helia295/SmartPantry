"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-24 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_images_user_id", "images", ["user_id"], unique=False)

    op.create_table(
        "detection_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_detection_sessions_image_id", "detection_sessions", ["image_id"], unique=False)
    op.create_index("ix_detection_sessions_user_id", "detection_sessions", ["user_id"], unique=False)

    op.create_table(
        "detection_proposals",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("label_raw", sa.String(length=255), nullable=False),
        sa.Column("label_normalized", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("quantity_suggested", sa.Float(), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("category_suggested", sa.String(length=64), nullable=True),
        sa.Column("is_perishable_suggested", sa.Boolean(), nullable=True),
        sa.Column("bbox_x", sa.Float(), nullable=True),
        sa.Column("bbox_y", sa.Float(), nullable=True),
        sa.Column("bbox_w", sa.Float(), nullable=True),
        sa.Column("bbox_h", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["detection_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_detection_proposals_session_id", "detection_proposals", ["session_id"], unique=False)

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_perishable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"], unique=False)

    op.create_table(
        "inventory_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("proposal_id", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("delta_quantity", sa.Float(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposal_id"], ["detection_proposals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["detection_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_inventory_change_logs_inventory_item_id", "inventory_change_logs", ["inventory_item_id"], unique=False)
    op.create_index("ix_inventory_change_logs_proposal_id", "inventory_change_logs", ["proposal_id"], unique=False)
    op.create_index("ix_inventory_change_logs_session_id", "inventory_change_logs", ["session_id"], unique=False)
    op.create_index("ix_inventory_change_logs_user_id", "inventory_change_logs", ["user_id"], unique=False)

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("prep_minutes", sa.Integer(), nullable=True),
        sa.Column("cook_minutes", sa.Integer(), nullable=True),
        sa.Column("total_minutes", sa.Integer(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("cuisine", sa.String(length=120), nullable=True),
        sa.Column("dietary_tags_json", sa.Text(), nullable=False),
        sa.Column("nutrition_json", sa.Text(), nullable=False),
        sa.Column("instructions_text", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_recipes_cuisine", "recipes", ["cuisine"], unique=False)
    op.create_index("ix_recipes_slug", "recipes", ["slug"], unique=True)
    op.create_index("ix_recipes_title", "recipes", ["title"], unique=False)
    op.create_index("ix_recipes_total_minutes", "recipes", ["total_minutes"], unique=False)

    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_raw", sa.Text(), nullable=False),
        sa.Column("ingredient_normalized", sa.String(length=255), nullable=False),
        sa.Column("quantity_text", sa.String(length=120), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recipe_ingredients_ingredient_normalized", "recipe_ingredients", ["ingredient_normalized"], unique=False)
    op.create_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"], unique=False)

    op.create_table(
        "recipe_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_feedback_user_recipe"),
    )
    op.create_index("ix_recipe_feedback_recipe_id", "recipe_feedback", ["recipe_id"], unique=False)
    op.create_index("ix_recipe_feedback_user_id", "recipe_feedback", ["user_id"], unique=False)

    op.create_table(
        "recipe_tags",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tag_name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "tag_name", name="uq_recipe_tag_user_name"),
    )
    op.create_index("ix_recipe_tags_tag_name", "recipe_tags", ["tag_name"], unique=False)
    op.create_index("ix_recipe_tags_user_id", "recipe_tags", ["user_id"], unique=False)

    op.create_table(
        "recipe_tag_links",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["recipe_tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "recipe_id", "tag_id", name="uq_recipe_tag_link_user_recipe_tag"),
    )
    op.create_index("ix_recipe_tag_links_recipe_id", "recipe_tag_links", ["recipe_id"], unique=False)
    op.create_index("ix_recipe_tag_links_tag_id", "recipe_tag_links", ["tag_id"], unique=False)
    op.create_index("ix_recipe_tag_links_user_id", "recipe_tag_links", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipe_tag_links_user_id", table_name="recipe_tag_links")
    op.drop_index("ix_recipe_tag_links_tag_id", table_name="recipe_tag_links")
    op.drop_index("ix_recipe_tag_links_recipe_id", table_name="recipe_tag_links")
    op.drop_table("recipe_tag_links")

    op.drop_index("ix_recipe_tags_user_id", table_name="recipe_tags")
    op.drop_index("ix_recipe_tags_tag_name", table_name="recipe_tags")
    op.drop_table("recipe_tags")

    op.drop_index("ix_recipe_feedback_user_id", table_name="recipe_feedback")
    op.drop_index("ix_recipe_feedback_recipe_id", table_name="recipe_feedback")
    op.drop_table("recipe_feedback")

    op.drop_index("ix_recipe_ingredients_recipe_id", table_name="recipe_ingredients")
    op.drop_index("ix_recipe_ingredients_ingredient_normalized", table_name="recipe_ingredients")
    op.drop_table("recipe_ingredients")

    op.drop_index("ix_recipes_total_minutes", table_name="recipes")
    op.drop_index("ix_recipes_title", table_name="recipes")
    op.drop_index("ix_recipes_slug", table_name="recipes")
    op.drop_index("ix_recipes_cuisine", table_name="recipes")
    op.drop_table("recipes")

    op.drop_index("ix_inventory_change_logs_user_id", table_name="inventory_change_logs")
    op.drop_index("ix_inventory_change_logs_session_id", table_name="inventory_change_logs")
    op.drop_index("ix_inventory_change_logs_proposal_id", table_name="inventory_change_logs")
    op.drop_index("ix_inventory_change_logs_inventory_item_id", table_name="inventory_change_logs")
    op.drop_table("inventory_change_logs")

    op.drop_index("ix_inventory_items_user_id", table_name="inventory_items")
    op.drop_table("inventory_items")

    op.drop_index("ix_detection_proposals_session_id", table_name="detection_proposals")
    op.drop_table("detection_proposals")

    op.drop_index("ix_detection_sessions_user_id", table_name="detection_sessions")
    op.drop_index("ix_detection_sessions_image_id", table_name="detection_sessions")
    op.drop_table("detection_sessions")

    op.drop_index("ix_images_user_id", table_name="images")
    op.drop_table("images")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
