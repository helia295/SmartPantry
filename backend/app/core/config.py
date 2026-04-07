import os
from functools import lru_cache
from pathlib import Path
from typing import List

_SKIP_DOTENV = os.getenv("SKIP_DOTENV", "").strip().lower() in {"1", "true", "yes", "on"}
if not _SKIP_DOTENV:
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
        self.image_cleanup_interval_minutes: int = int(
            os.getenv("IMAGE_CLEANUP_INTERVAL_MINUTES", "30")
        )
        self.image_cleanup_batch_limit: int = int(
            os.getenv("IMAGE_CLEANUP_BATCH_LIMIT", "200")
        )

        # Detection provider configuration.
        # Prefer YOLO for local demos and only fall back to mock at runtime if
        # model inference or its dependencies are unavailable.
        self.detection_provider: str = os.getenv("DETECTION_PROVIDER", "yolo")
        self.yolo_model_name: str = os.getenv("YOLO_MODEL_NAME", "yolov8n.pt")
        self.detection_confidence_threshold: float = float(
            os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.35")
        )
        self.yolo_inference_size: int = int(os.getenv("YOLO_INFERENCE_SIZE", "960"))
        self.yolo_max_image_dim: int = int(os.getenv("YOLO_MAX_IMAGE_DIM", "1600"))

        # OpenAI-backed recipe assistant configuration.
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.openai_assistant_enabled: bool = (
            os.getenv("OPENAI_ASSISTANT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.openai_assistant_preview_only: bool = (
            os.getenv("OPENAI_ASSISTANT_PREVIEW_ONLY", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.openai_assistant_timeout_seconds: int = int(
            os.getenv("OPENAI_ASSISTANT_TIMEOUT_SECONDS", "20")
        )
        self.openai_assistant_max_recipes: int = int(
            os.getenv("OPENAI_ASSISTANT_MAX_RECIPES", "5")
        )
        self.openai_assistant_max_pantry_items: int = int(
            os.getenv("OPENAI_ASSISTANT_MAX_PANTRY_ITEMS", "25")
        )
        self.openai_embedding_model: str = os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.openai_rag_enabled: bool = (
            os.getenv("OPENAI_RAG_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.openai_rag_preview_only: bool = (
            os.getenv("OPENAI_RAG_PREVIEW_ONLY", "false").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.openai_rag_timeout_seconds: int = int(
            os.getenv("OPENAI_RAG_TIMEOUT_SECONDS", "25")
        )
        self.openai_rag_max_retrievals: int = int(
            os.getenv("OPENAI_RAG_MAX_RETRIEVALS", "8")
        )
        self.openai_rag_max_context_recipes: int = int(
            os.getenv("OPENAI_RAG_MAX_CONTEXT_RECIPES", "5")
        )
        self.openai_features_repo_url: str = os.getenv(
            "OPENAI_FEATURES_REPO_URL",
            "https://github.com/heliadinh/SmartPantry",
        )

        # Lightweight in-memory rate limiting.
        # This is intended as a practical deployment safeguard for a single-instance app.
        self.auth_rate_limit_requests: int = int(
            os.getenv("AUTH_RATE_LIMIT_REQUESTS", "10")
        )
        self.auth_rate_limit_window_seconds: int = int(
            os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
        )
        self.register_rate_limit_requests: int = int(
            os.getenv("REGISTER_RATE_LIMIT_REQUESTS", "5")
        )
        self.register_rate_limit_window_seconds: int = int(
            os.getenv("REGISTER_RATE_LIMIT_WINDOW_SECONDS", "300")
        )
        self.image_upload_rate_limit_requests: int = int(
            os.getenv("IMAGE_UPLOAD_RATE_LIMIT_REQUESTS", "12")
        )
        self.image_upload_rate_limit_window_seconds: int = int(
            os.getenv("IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS", "300")
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

        if (self.openai_assistant_enabled or self.openai_rag_enabled) and not self.openai_api_key:
            warnings.append(
                "OpenAI-backed features are enabled but OPENAI_API_KEY is missing. Assistant routes will be unavailable unless preview mode is enabled."
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
