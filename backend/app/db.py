from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# For SQLite we need check_same_thread=False for use with FastAPI.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
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
