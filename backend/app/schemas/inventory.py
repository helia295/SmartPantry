from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InventoryItemBase(BaseModel):
    name: str
    quantity: float = 1.0
    unit: str = "count"
    category: Optional[str] = None
    is_perishable: bool = False


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    is_perishable: Optional[bool] = None
    refresh_created_at: Optional[bool] = None


class InventoryItemRead(InventoryItemBase):
    id: int
    user_id: int
    normalized_name: str
    created_at: Optional[datetime] = None
    last_updated: datetime

    class Config:
        from_attributes = True
