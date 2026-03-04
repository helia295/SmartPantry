from __future__ import annotations

from pathlib import Path

import boto3
from botocore.config import Config

from app.core.config import get_settings


class StorageService:
    def save_bytes(self, storage_key: str, content: bytes, content_type: str) -> None:
        raise NotImplementedError

    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    def read_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        return self.base_dir / storage_key

    def save_bytes(self, storage_key: str, content: bytes, content_type: str) -> None:
        path = self._resolve_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def delete(self, storage_key: str) -> None:
        path = self._resolve_path(storage_key)
        if path.exists():
            path.unlink()

    def read_bytes(self, storage_key: str) -> bytes:
        path = self._resolve_path(storage_key)
        return path.read_bytes()


class R2StorageService(StorageService):
    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ) -> None:
        self.bucket_name = bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def save_bytes(self, storage_key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=storage_key,
            Body=content,
            ContentType=content_type,
        )

    def delete(self, storage_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket_name, Key=storage_key)

    def read_bytes(self, storage_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=storage_key)
        return response["Body"].read()


def get_storage_service() -> StorageService:
    settings = get_settings()
    provider = settings.storage_provider.strip().lower()

    if provider == "local":
        return LocalStorageService(base_dir=settings.local_storage_dir)

    if provider == "r2":
        required = [
            settings.r2_endpoint,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        ]
        if any(not value for value in required):
            raise RuntimeError("R2 storage selected but required R2 environment variables are missing")

        return R2StorageService(
            endpoint_url=settings.r2_endpoint,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket_name=settings.r2_bucket_name,
        )

    raise RuntimeError(f"Unsupported storage provider: {settings.storage_provider}")
