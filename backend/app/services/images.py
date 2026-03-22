from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Image
from app.services.storage import get_storage_service


def cleanup_expired_images(db: Session, *, limit: int = 200) -> int:
    now = datetime.now(timezone.utc)
    expired_images = (
        db.query(Image)
        .filter(
            Image.deleted_at.is_(None),
            Image.expires_at <= now,
        )
        .order_by(Image.expires_at.asc(), Image.id.asc())
        .limit(limit)
        .all()
    )
    if not expired_images:
        return 0

    storage = get_storage_service()
    for image in expired_images:
        try:
            storage.delete(image.storage_key)
        except Exception:
            # Lifecycle rules or prior failures may already have removed the object.
            pass
        image.deleted_at = now
        db.add(image)

    db.commit()
    return len(expired_images)
