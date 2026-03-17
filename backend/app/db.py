from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# For SQLite we need check_same_thread=False for use with FastAPI.
engine = create_engine(
    settings.database_url,
    connect_args=(
        {"check_same_thread": False, "timeout": 30}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """
    FastAPI dependency that provides a database session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema_compatibility() -> None:
    """
    Temporary schema compatibility for local SQLite when running without migrations.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        inventory_table = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_items'"
        ).first()
        if inventory_table is not None:
            inventory_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(inventory_items)").fetchall()
            }
            if "created_at" not in inventory_columns:
                conn.exec_driver_sql("ALTER TABLE inventory_items ADD COLUMN created_at DATETIME")
                conn.exec_driver_sql(
                    "UPDATE inventory_items SET created_at = last_updated WHERE created_at IS NULL"
                )

        users_table = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).first()
        if users_table is not None:
            user_columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
            }
            if "timezone" not in user_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"
                )

        proposals_table = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='detection_proposals'"
        ).first()
        if proposals_table is not None:
            proposal_columns = {
                row[1]
                for row in conn.exec_driver_sql("PRAGMA table_info(detection_proposals)").fetchall()
            }
            if "bbox_x" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN bbox_x FLOAT")
            if "bbox_y" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN bbox_y FLOAT")
            if "bbox_w" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN bbox_w FLOAT")
            if "bbox_h" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN bbox_h FLOAT")
            if "category_suggested" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN category_suggested VARCHAR(64)")
            if "is_perishable_suggested" not in proposal_columns:
                conn.exec_driver_sql("ALTER TABLE detection_proposals ADD COLUMN is_perishable_suggested BOOLEAN")
            if "source" not in proposal_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE detection_proposals ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'auto'"
                )

        recipes_table = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recipes'"
        ).first()
        if recipes_table is not None:
            recipe_columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(recipes)").fetchall()
            }
            if "rating" not in recipe_columns:
                try:
                    conn.exec_driver_sql("ALTER TABLE recipes ADD COLUMN rating FLOAT")
                except OperationalError as exc:
                    if "duplicate column name: rating" not in str(exc).lower():
                        raise
