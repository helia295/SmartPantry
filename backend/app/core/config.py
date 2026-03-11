import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_PATH)


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

    # Storage provider (local, r2).
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "local")

    # Upload constraints and retention.
    max_upload_images: int = int(os.getenv("MAX_UPLOAD_IMAGES", "3"))
    max_image_size_mb: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
    image_retention_days: int = int(os.getenv("IMAGE_RETENTION_DAYS", "7"))

    # Detection provider configuration.
    # Prefer YOLO for local demos and only fall back to mock at runtime if
    # model inference or its dependencies are unavailable.
    detection_provider: str = os.getenv("DETECTION_PROVIDER", "yolo")
    yolo_model_name: str = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
    detection_confidence_threshold: float = float(
        os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.35")
    )

    # Local storage path for development fallback.
    local_storage_dir: str = os.getenv("LOCAL_STORAGE_DIR", "./storage")

    # Cloudflare R2 configuration.
    cf_account_id: str = os.getenv("CF_ACCOUNT_ID", "")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_endpoint: str = os.getenv("R2_ENDPOINT", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
