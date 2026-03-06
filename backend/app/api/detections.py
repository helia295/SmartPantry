from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import DetectionProposal, DetectionSession, Image, User
from app.schemas import (
    DetectionProposalRead,
    DetectionProposalUpdate,
    DetectionSessionDetailResponse,
    ManualProposalCreate,
)
from app.services.detection import aggregate_auto_proposals, detect_manual_region
from app.services.storage import get_storage_service


router = APIRouter()


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
