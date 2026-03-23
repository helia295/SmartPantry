from datetime import datetime
from typing import Literal, Optional

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
    category_suggested: Optional[str] = None
    is_perishable_suggested: Optional[bool] = None
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    source: str
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
    detection_session_id: Optional[int] = None
    detection_session_status: Optional[str] = None
    pending_proposal_count: Optional[int] = None

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


class ManualProposalCreate(BaseModel):
    x: float
    y: float
    w: float = 0.22
    h: float = 0.22
    label_hint: Optional[str] = None


class DetectionProposalUpdate(BaseModel):
    label_raw: Optional[str] = None
    quantity_suggested: Optional[float] = None
    quantity_unit: Optional[str] = None
    category_suggested: Optional[str] = None
    is_perishable_suggested: Optional[bool] = None
    state: Optional[str] = None


class DetectionConfirmAction(BaseModel):
    proposal_id: int
    action: Literal["add_new", "update_existing", "reject"]
    target_item_id: Optional[int] = None
    apply_grouped_label: bool = False
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    is_perishable: Optional[bool] = None


class DetectionConfirmRequest(BaseModel):
    actions: list[DetectionConfirmAction]


class DetectionConfirmResult(BaseModel):
    processed: int
    added: int
    updated: int
    rejected: int
    logs_created: int
