from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db import get_db
from app.models import DetectionProposal, DetectionSession, Image, User
from app.schemas import (
    ImageListResponse,
    ImageUploadResponse,
    ImageUploadResult,
)
from app.services.detection import run_mock_detection
from app.services.storage import get_storage_service


router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def build_storage_key(user_id: int, original_name: str) -> str:
    safe_name = Path(original_name).name.replace(" ", "_")
    return f"users/{user_id}/images/{uuid4().hex}_{safe_name}"


@router.get("", response_model=ImageListResponse)
def list_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImageListResponse:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Image)
        .filter(
            Image.user_id == current_user.id,
            Image.deleted_at.is_(None),
            Image.expires_at > now,
        )
        .order_by(Image.created_at.desc())
        .all()
    )
    return ImageListResponse(results=rows)


@router.post("", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_images(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImageUploadResponse:
    settings = get_settings()
    if len(files) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")
    if len(files) > settings.max_upload_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Max {settings.max_upload_images} images per upload",
        )

    max_bytes = settings.max_image_size_mb * 1024 * 1024
    storage = get_storage_service()
    uploaded_keys: list[str] = []
    results: list[ImageUploadResult] = []

    try:
        for file in files:
            content_type = (file.content_type or "").lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported content type: {file.content_type}",
                )

            content = await file.read()
            size_bytes = len(content)
            if size_bytes == 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded")
            if size_bytes > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{file.filename}' exceeds {settings.max_image_size_mb}MB limit",
                )

            storage_key = build_storage_key(current_user.id, file.filename or "upload.jpg")
            storage.save_bytes(storage_key=storage_key, content=content, content_type=content_type)
            uploaded_keys.append(storage_key)

            now = datetime.now(timezone.utc)
            image = Image(
                user_id=current_user.id,
                storage_key=storage_key,
                original_filename=file.filename or "upload.jpg",
                content_type=content_type,
                size_bytes=size_bytes,
                expires_at=now + timedelta(days=settings.image_retention_days),
            )
            db.add(image)
            db.flush()

            session = DetectionSession(
                user_id=current_user.id,
                image_id=image.id,
                status="pending",
                model_version="mock-v0",
            )
            db.add(session)
            db.flush()

            # Placeholder detection for Milestone 4 scaffolding.
            mock = run_mock_detection(image.original_filename)
            proposal = DetectionProposal(session_id=session.id, **mock)
            db.add(proposal)

            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            db.add(session)
            db.flush()

            results.append(ImageUploadResult(image=image, detection_session=session))

        db.commit()
        return ImageUploadResponse(results=results)
    except HTTPException:
        db.rollback()
        for key in uploaded_keys:
            try:
                storage.delete(key)
            except Exception:
                pass
        raise
    except Exception:
        db.rollback()
        for key in uploaded_keys:
            try:
                storage.delete(key)
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")
