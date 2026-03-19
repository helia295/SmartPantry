import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv


BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_PATH)


def parse_csv_env(raw_value: str) -> List[str]:
    return [part.strip() for part in raw_value.split(",") if part.strip()]


class Settings:
    """
    Central configuration for the backend.

    For now we keep this minimal and avoid extra dependencies.
    """

    def __init__(self) -> None:
        # SQLite file for local development.
        # Example: sqlite:///./smartpantry.db
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "sqlite:///./smartpantry.db",
        )

        # App environment.
        # Used to distinguish local-development-safe defaults from deployment posture.
        self.app_env: str = os.getenv("APP_ENV", "development").strip().lower()

        # JWT configuration.
        # In development we fall back to a hard-coded secret so the app
        # works out of the box. For any real deployment you MUST override
        # this via the JWT_SECRET environment variable and keep it private.
        self.jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        # CORS configuration.
        # Keep localhost enabled by default for local frontend development.
        self.cors_origins: List[str] = parse_csv_env(
            os.getenv("CORS_ORIGINS", "http://localhost:3000")
        )

        # Storage provider (local, r2).
        self.storage_provider: str = os.getenv("STORAGE_PROVIDER", "local")

        # Upload constraints and retention.
        self.max_upload_images: int = int(os.getenv("MAX_UPLOAD_IMAGES", "3"))
        self.max_image_size_mb: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))
        self.image_retention_days: int = int(os.getenv("IMAGE_RETENTION_DAYS", "7"))

        # Detection provider configuration.
        # Prefer YOLO for local demos and only fall back to mock at runtime if
        # model inference or its dependencies are unavailable.
        self.detection_provider: str = os.getenv("DETECTION_PROVIDER", "yolo")
        self.yolo_model_name: str = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
        self.detection_confidence_threshold: float = float(
            os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.35")
        )

        # Local storage path for development fallback.
        self.local_storage_dir: str = os.getenv("LOCAL_STORAGE_DIR", "./storage")

        # Cloudflare R2 configuration.
        self.cf_account_id: str = os.getenv("CF_ACCOUNT_ID", "")
        self.r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "")
        self.r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
        self.r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.r2_endpoint: str = os.getenv("R2_ENDPOINT", "")

    def is_production(self) -> bool:
        return self.app_env == "production"

    def deployment_warnings(self) -> List[str]:
        warnings: List[str] = []

        if not self.is_production():
            return warnings

        if self.jwt_secret == "dev-secret-change-me":
            warnings.append(
                "JWT_SECRET is still using the development fallback. Set a strong secret for production."
            )

        if self.database_url.startswith("sqlite:"):
            warnings.append(
                "DATABASE_URL is still pointing at SQLite. Use PostgreSQL or another production database for deployment."
            )

        if self.storage_provider == "local":
            warnings.append(
                "STORAGE_PROVIDER is set to local. Production deployments should usually use object storage such as Cloudflare R2."
            )

        if not self.cors_origins:
            warnings.append(
                "CORS_ORIGINS is empty. Browser clients will fail to access the backend unless trusted frontend origins are configured."
            )
        elif any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins):
            warnings.append(
                "CORS_ORIGINS still contains localhost-style origins. Replace them with your real deployed frontend origins in production."
            )

        return warnings


@lru_cache()
def get_settings() -> Settings:
    return Settings()
