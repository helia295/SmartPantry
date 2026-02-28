from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models import DetectionProposal, DetectionSession, User
from app.schemas import DetectionSessionDetailResponse


router = APIRouter()


@router.get("/{session_id}", response_model=DetectionSessionDetailResponse)
def get_detection_session(
    session_id: int,
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
    return DetectionSessionDetailResponse(session=session, proposals=proposals)
