import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import (
    DetectionProposal,
    DetectionSession,
    Image,
    InventoryChangeLog,
    InventoryItem,
    User,
)
from app.schemas import (
    DetectionConfirmRequest,
    DetectionConfirmResult,
    DetectionProposalRead,
    DetectionProposalUpdate,
    DetectionSessionDetailResponse,
    ManualProposalCreate,
)
from app.services.detection import aggregate_auto_proposals, detect_manual_region
from app.services.storage import get_storage_service


router = APIRouter()


def normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


@router.get("/{session_id}", response_model=DetectionSessionDetailResponse)
def get_detection_session(
    session_id: int,
    view: str = Query("grouped", pattern="^(grouped|boxes)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DetectionSessionDetailResponse:
    session = (
        db.query(DetectionSession)
        .filter(DetectionSession.id == session_id, DetectionSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection session not found")

    proposals = (
        db.query(DetectionProposal)
        .filter(DetectionProposal.session_id == session.id)
        .order_by(DetectionProposal.id.asc())
        .all()
    )
    if view == "grouped":
        proposals = aggregate_auto_proposals(proposals)
    return DetectionSessionDetailResponse(session=session, proposals=proposals)


@router.post("/{session_id}/manual-proposals", response_model=DetectionProposalRead, status_code=201)
def create_manual_proposal(
    session_id: int,
    payload: ManualProposalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DetectionProposalRead:
    session = (
        db.query(DetectionSession)
        .filter(DetectionSession.id == session_id, DetectionSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection session not found")

    if payload.x < 0 or payload.x > 1 or payload.y < 0 or payload.y > 1:
        raise HTTPException(status_code=400, detail="x and y must be normalized between 0 and 1")

    image = (
        db.query(Image)
        .filter(Image.id == session.image_id, Image.user_id == current_user.id, Image.deleted_at.is_(None))
        .first()
    )
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    storage = get_storage_service()
    try:
        image_bytes = storage.read_bytes(image.storage_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image object not found")

    base = detect_manual_region(
        image_bytes=image_bytes,
        x=payload.x,
        y=payload.y,
        w=payload.w,
        h=payload.h,
        label_hint=payload.label_hint,
    )
    proposal = DetectionProposal(
        session_id=session.id,
        **base,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.patch("/{session_id}/proposals/{proposal_id}", response_model=DetectionProposalRead)
def update_proposal(
    session_id: int,
    proposal_id: int,
    payload: DetectionProposalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DetectionProposalRead:
    session = (
        db.query(DetectionSession)
        .filter(DetectionSession.id == session_id, DetectionSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection session not found")

    proposal = (
        db.query(DetectionProposal)
        .filter(DetectionProposal.id == proposal_id, DetectionProposal.session_id == session.id)
        .first()
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    updates = payload.model_dump(exclude_unset=True)
    if "label_raw" in updates and updates["label_raw"] is not None:
        proposal.label_raw = updates["label_raw"].strip()
        proposal.label_normalized = proposal.label_raw.lower().strip()

    for field in [
        "quantity_suggested",
        "quantity_unit",
        "category_suggested",
        "is_perishable_suggested",
        "state",
    ]:
        if field in updates:
            setattr(proposal, field, updates[field])

    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/{session_id}/confirm", response_model=DetectionConfirmResult)
def confirm_detection_session(
    session_id: int,
    payload: DetectionConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DetectionConfirmResult:
    session = (
        db.query(DetectionSession)
        .filter(DetectionSession.id == session_id, DetectionSession.user_id == current_user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection session not found")
    if not payload.actions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No actions provided")

    proposal_map = {
        p.id: p
        for p in db.query(DetectionProposal)
        .filter(DetectionProposal.session_id == session.id)
        .all()
    }

    added = 0
    updated = 0
    rejected = 0
    logs_created = 0

    for action in payload.actions:
        proposal = proposal_map.get(action.proposal_id)
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Proposal {action.proposal_id} does not belong to this session",
            )

        confirmed_name = (action.name or proposal.label_raw or "unknown item").strip()
        confirmed_quantity = (
            action.quantity if action.quantity is not None else (proposal.quantity_suggested or 1.0)
        )
        confirmed_unit = action.unit or proposal.quantity_unit or "count"
        confirmed_category = (
            action.category if action.category is not None else proposal.category_suggested
        )
        confirmed_perishable = (
            action.is_perishable
            if action.is_perishable is not None
            else bool(proposal.is_perishable_suggested)
        )

        proposal.label_raw = confirmed_name
        proposal.label_normalized = normalize_name(confirmed_name)
        proposal.quantity_suggested = float(confirmed_quantity)
        proposal.quantity_unit = confirmed_unit
        proposal.category_suggested = confirmed_category
        proposal.is_perishable_suggested = confirmed_perishable

        if action.action == "reject":
            proposal.state = "rejected"
            rejected += 1
            log = InventoryChangeLog(
                user_id=current_user.id,
                inventory_item_id=None,
                session_id=session.id,
                proposal_id=proposal.id,
                change_type="reject",
                delta_quantity=None,
                details_json=json.dumps(
                    {
                        "label": confirmed_name,
                        "quantity": confirmed_quantity,
                        "unit": confirmed_unit,
                        "category": confirmed_category,
                    }
                ),
            )
            db.add(log)
            logs_created += 1
            continue

        target_item: Optional[InventoryItem] = None
        if action.action == "add_new":
            target_item = InventoryItem(
                user_id=current_user.id,
                name=confirmed_name,
                normalized_name=normalize_name(confirmed_name),
                quantity=float(confirmed_quantity),
                unit=confirmed_unit,
                category=confirmed_category,
                is_perishable=confirmed_perishable,
            )
            db.add(target_item)
            db.flush()
            added += 1
            change_type = "add"
            delta_quantity = float(confirmed_quantity)
        else:
            if action.target_item_id is not None:
                target_item = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.id == action.target_item_id,
                        InventoryItem.user_id == current_user.id,
                    )
                    .first()
                )
            if target_item is None:
                target_item = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.user_id == current_user.id,
                        InventoryItem.normalized_name == normalize_name(confirmed_name),
                    )
                    .order_by(InventoryItem.id.asc())
                    .first()
                )
            if target_item is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No target inventory item found for proposal {proposal.id}",
                )

            target_item.quantity = float(target_item.quantity) + float(confirmed_quantity)
            if action.unit is not None:
                target_item.unit = confirmed_unit
            if action.category is not None:
                target_item.category = confirmed_category
            if action.is_perishable is not None:
                target_item.is_perishable = confirmed_perishable
            db.add(target_item)
            updated += 1
            change_type = "update"
            delta_quantity = float(confirmed_quantity)

        proposal.state = "accepted"
        db.add(proposal)
        log = InventoryChangeLog(
            user_id=current_user.id,
            inventory_item_id=target_item.id if target_item is not None else None,
            session_id=session.id,
            proposal_id=proposal.id,
            change_type=change_type,
            delta_quantity=delta_quantity,
            details_json=json.dumps(
                {
                    "name": confirmed_name,
                    "quantity": confirmed_quantity,
                    "unit": confirmed_unit,
                    "category": confirmed_category,
                    "is_perishable": confirmed_perishable,
                }
            ),
        )
        db.add(log)
        logs_created += 1

    db.commit()
    return DetectionConfirmResult(
        processed=len(payload.actions),
        added=added,
        updated=updated,
        rejected=rejected,
        logs_created=logs_created,
    )
