from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import InventoryItem, User
from app.schemas.inventory import InventoryItemCreate, InventoryItemRead, InventoryItemUpdate


router = APIRouter()


def normalize_name(name: str) -> str:
    return name.strip().lower()


@router.post("", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item_in: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryItemRead:
    item = InventoryItem(
        user_id=current_user.id,
        name=item_in.name.strip(),
        normalized_name=normalize_name(item_in.name),
        quantity=item_in.quantity,
        unit=item_in.unit,
        category=item_in.category,
        is_perishable=item_in.is_perishable,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[InventoryItemRead])
def list_inventory_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InventoryItemRead]:
    return (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == current_user.id)
        .order_by(InventoryItem.last_updated.desc())
        .all()
    )


@router.patch("/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: int,
    item_in: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryItemRead:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id, InventoryItem.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    updates = item_in.model_dump(exclude_unset=True)
    refresh_created_at = bool(updates.pop("refresh_created_at", False))
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()
        updates["normalized_name"] = normalize_name(updates["name"])

    for key, value in updates.items():
        setattr(item, key, value)

    if refresh_created_at:
        item.created_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id, InventoryItem.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
