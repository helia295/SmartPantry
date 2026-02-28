from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DetectionSessionRead(BaseModel):
    id: int
    image_id: int
    user_id: int
    status: str
    model_version: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class DetectionProposalRead(BaseModel):
    id: int
    session_id: int
    label_raw: str
    label_normalized: str
    confidence: Optional[float] = None
    quantity_suggested: Optional[float] = None
    quantity_unit: Optional[str] = None
    state: str

    class Config:
        from_attributes = True


class ImageRead(BaseModel):
    id: int
    user_id: int
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    expires_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImageUploadResult(BaseModel):
    image: ImageRead
    detection_session: DetectionSessionRead


class ImageUploadResponse(BaseModel):
    results: list[ImageUploadResult]


class ImageListResponse(BaseModel):
    results: list[ImageRead]


class DetectionSessionDetailResponse(BaseModel):
    session: DetectionSessionRead
    proposals: list[DetectionProposalRead]
