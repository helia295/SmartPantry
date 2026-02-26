import os
from functools import lru_cache


class Settings:
    """
    Central configuration for the backend.

    For now we keep this minimal and avoid extra dependencies.
    Later we can extend with JWT settings, CORS, etc.
    """

    # SQLite file for local development.
    # Example: sqlite:///./smartpantry.db
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./smartpantry.db",
    )

    # JWT configuration.
    # In development we fall back to a hard-coded secret so the app
    # works out of the box. For any real deployment you MUST override
    # this via the JWT_SECRET environment variable and keep it private.
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

