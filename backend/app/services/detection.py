from __future__ import annotations

import io
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)

def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def infer_label_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"\d+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "unknown item"
    return cleaned


def run_mock_detection(original_filename: str) -> dict:
    """
    Minimal placeholder for M4 until model inference is integrated.
    """
    label_raw = infer_label_from_filename(original_filename)
    normalized = normalize_label(label_raw)
    category, perishable = suggest_attributes(normalized)
    return {
        "label_raw": label_raw,
        "label_normalized": normalized,
        "confidence": 0.35,
        "quantity_suggested": 1.0,
        "quantity_unit": "count",
        "category_suggested": category,
        "is_perishable_suggested": perishable,
        # Normalized bbox coordinates for UI overlay (0..1 relative to image size).
        "bbox_x": 0.2,
        "bbox_y": 0.2,
        "bbox_w": 0.45,
        "bbox_h": 0.45,
        "source": "auto",
        "state": "pending",
    }


def run_detection(image_bytes: bytes, original_filename: str) -> tuple[list[dict], str]:
    settings = get_settings()
    provider = settings.detection_provider.strip().lower()

    if provider == "mock":
        return [run_mock_detection(original_filename)], "mock-v0"

    if provider != "yolo":
        raise RuntimeError(f"Unsupported detection provider: {settings.detection_provider}")

    try:
        proposals = run_yolo_detection(
            image_bytes=image_bytes,
            confidence_threshold=settings.detection_confidence_threshold,
            model_name=settings.yolo_model_name,
            inference_size=settings.yolo_inference_size,
            max_image_dim=settings.yolo_max_image_dim,
        )
        model_version = f"yolo-{settings.yolo_model_name}"
        if proposals:
            return proposals, model_version
        return [run_mock_detection(original_filename)], f"{model_version}-empty-fallback"
    except Exception:
        logger.exception("YOLO inference failed, falling back to mock detection")
        return [run_mock_detection(original_filename)], "mock-v0-fallback"


@lru_cache(maxsize=2)
def _load_yolo_model(model_name: str):
    os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")
    from ultralytics import YOLO

    return YOLO(model_name)


def preload_detection_backend() -> None:
    settings = get_settings()
    provider = settings.detection_provider.strip().lower()
    if provider != "yolo":
        return

    logger.info("Preloading YOLO model '%s' for detection warmup.", settings.yolo_model_name)
    _load_yolo_model(settings.yolo_model_name)


def _open_image_for_detection(image_bytes: bytes):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for YOLO inference") from exc

    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _prepare_image_for_detection(image, max_image_dim: int):
    if max_image_dim > 0:
        image.thumbnail((max_image_dim, max_image_dim))
    return image


def run_yolo_detection(
    image_bytes: bytes,
    confidence_threshold: float,
    model_name: str,
    inference_size: int,
    max_image_dim: int,
) -> list[dict]:
    image = _open_image_for_detection(image_bytes)
    image = _prepare_image_for_detection(image, max_image_dim=max_image_dim)

    model = _load_yolo_model(model_name)
    width, height = image.size
    if width <= 0 or height <= 0:
        return []

    results = model.predict(
        source=image,
        conf=confidence_threshold,
        verbose=False,
        device="cpu",
        imgsz=inference_size,
    )
    if not results:
        return []

    result = results[0]
    names = result.names if hasattr(result, "names") else {}
    boxes = result.boxes
    if boxes is None:
        return []

    proposals: list[dict] = []
    for box in boxes:
        cls_id = int(box.cls[0].item()) if box.cls is not None else -1
        confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
        coords = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
        x1, y1, x2, y2 = [float(v) for v in coords]

        if x2 <= x1 or y2 <= y1:
            continue

        label_raw = str(names.get(cls_id, f"class-{cls_id}")).replace("_", " ")
        label_normalized = normalize_label(label_raw)
        category, perishable = suggest_attributes(label_normalized)

        proposals.append(
            {
                "label_raw": label_raw,
                "label_normalized": label_normalized,
                "confidence": confidence,
                "quantity_suggested": 1.0,
                "quantity_unit": "count",
                "category_suggested": category,
                "is_perishable_suggested": perishable,
                "bbox_x": max(0.0, min(1.0, x1 / width)),
                "bbox_y": max(0.0, min(1.0, y1 / height)),
                "bbox_w": max(0.0, min(1.0, (x2 - x1) / width)),
                "bbox_h": max(0.0, min(1.0, (y2 - y1) / height)),
                "source": "auto",
                "state": "pending",
            }
        )
    return proposals


def aggregate_auto_proposals(proposals: list[Any]) -> list[dict]:
    """
    Aggregate auto-detected proposals by normalized label to reduce duplicates,
    while leaving manual proposals as independent entries.
    """
    grouped: dict[str, dict] = {}
    passthrough: list[dict] = []

    for proposal in proposals:
        source = getattr(proposal, "source", None) if not isinstance(proposal, dict) else proposal.get("source")
        state = getattr(proposal, "state", None) if not isinstance(proposal, dict) else proposal.get("state")
        if source != "auto" or state != "pending":
            passthrough.append(_proposal_to_dict(proposal))
            continue

        label_key = (
            getattr(proposal, "label_normalized", "") if not isinstance(proposal, dict) else proposal.get("label_normalized", "")
        ).strip()
        if not label_key:
            passthrough.append(_proposal_to_dict(proposal))
            continue

        current = _proposal_to_dict(proposal)
        bucket = grouped.get(label_key)
        if bucket is None:
            bucket = current
            bucket["quantity_suggested"] = float(bucket.get("quantity_suggested") or 1.0)
            grouped[label_key] = bucket
            continue

        bucket["quantity_suggested"] = float(bucket.get("quantity_suggested") or 0.0) + float(
            current.get("quantity_suggested") or 1.0
        )
        bucket["confidence"] = max(float(bucket.get("confidence") or 0.0), float(current.get("confidence") or 0.0))

        # Expand bbox to include all same-label detections.
        b1x = float(bucket.get("bbox_x") or 0.0)
        b1y = float(bucket.get("bbox_y") or 0.0)
        b1w = float(bucket.get("bbox_w") or 0.0)
        b1h = float(bucket.get("bbox_h") or 0.0)
        b2x = float(current.get("bbox_x") or 0.0)
        b2y = float(current.get("bbox_y") or 0.0)
        b2w = float(current.get("bbox_w") or 0.0)
        b2h = float(current.get("bbox_h") or 0.0)
        min_x = min(b1x, b2x)
        min_y = min(b1y, b2y)
        max_x = max(b1x + b1w, b2x + b2w)
        max_y = max(b1y + b1h, b2y + b2h)
        bucket["bbox_x"] = max(0.0, min(1.0, min_x))
        bucket["bbox_y"] = max(0.0, min(1.0, min_y))
        bucket["bbox_w"] = max(0.0, min(1.0, max_x - min_x))
        bucket["bbox_h"] = max(0.0, min(1.0, max_y - min_y))

    merged = list(grouped.values()) + passthrough
    merged.sort(key=lambda p: (p.get("id", 0), p.get("label_normalized", "")))
    return merged


def detect_manual_region(
    image_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
    label_hint: str | None = None,
) -> dict:
    """
    Try YOLO on a user-clicked crop region; fallback to hint-based/manual classification.
    """
    settings = get_settings()

    box_w = max(0.05, min(1.0, w))
    box_h = max(0.05, min(1.0, h))
    box_x = max(0.0, min(1.0, x - box_w / 2))
    box_y = max(0.0, min(1.0, y - box_h / 2))
    box_w = min(1.0 - box_x, box_w)
    box_h = min(1.0 - box_y, box_h)

    if settings.detection_provider.strip().lower() == "yolo":
        try:
            yolo_result = _detect_on_crop_with_yolo(
                image_bytes=image_bytes,
                crop_x=box_x,
                crop_y=box_y,
                crop_w=box_w,
                crop_h=box_h,
                confidence_threshold=settings.detection_confidence_threshold,
                model_name=settings.yolo_model_name,
                inference_size=settings.yolo_inference_size,
                max_image_dim=settings.yolo_max_image_dim,
            )
            if yolo_result is not None:
                yolo_result["source"] = "manual"
                yolo_result["state"] = "pending"
                return yolo_result
        except Exception:
            logger.exception("Manual crop YOLO inference failed; using fallback classification")

    fallback = classify_label_hint(label_hint or "manual item")
    fallback["bbox_x"] = box_x
    fallback["bbox_y"] = box_y
    fallback["bbox_w"] = box_w
    fallback["bbox_h"] = box_h
    return fallback


def _detect_on_crop_with_yolo(
    image_bytes: bytes,
    crop_x: float,
    crop_y: float,
    crop_w: float,
    crop_h: float,
    confidence_threshold: float,
    model_name: str,
    inference_size: int,
    max_image_dim: int,
) -> dict | None:
    image = _open_image_for_detection(image_bytes)
    width, height = image.size
    if width <= 0 or height <= 0:
        return None

    left = int(max(0, min(width - 1, round(crop_x * width))))
    top = int(max(0, min(height - 1, round(crop_y * height))))
    right = int(max(left + 1, min(width, round((crop_x + crop_w) * width))))
    bottom = int(max(top + 1, min(height, round((crop_y + crop_h) * height))))
    cropped = image.crop((left, top, right, bottom))

    cropped = _prepare_image_for_detection(cropped, max_image_dim=max_image_dim)
    buffer = io.BytesIO()
    cropped.save(buffer, format="JPEG", quality=90, optimize=True)
    crop_bytes = buffer.getvalue()
    candidates = run_yolo_detection(
        image_bytes=crop_bytes,
        confidence_threshold=confidence_threshold,
        model_name=model_name,
        inference_size=inference_size,
        max_image_dim=max_image_dim,
    )
    if not candidates:
        return None

    best = max(candidates, key=lambda p: float(p.get("confidence") or 0.0))
    best_x = crop_x + float(best.get("bbox_x") or 0.0) * crop_w
    best_y = crop_y + float(best.get("bbox_y") or 0.0) * crop_h
    best_w = float(best.get("bbox_w") or 0.0) * crop_w
    best_h = float(best.get("bbox_h") or 0.0) * crop_h
    best["bbox_x"] = max(0.0, min(1.0, best_x))
    best["bbox_y"] = max(0.0, min(1.0, best_y))
    best["bbox_w"] = max(0.0, min(1.0, best_w))
    best["bbox_h"] = max(0.0, min(1.0, best_h))
    return best


def _proposal_to_dict(proposal: Any) -> dict:
    if isinstance(proposal, dict):
        return dict(proposal)
    return {
        "id": proposal.id,
        "session_id": proposal.session_id,
        "label_raw": proposal.label_raw,
        "label_normalized": proposal.label_normalized,
        "confidence": proposal.confidence,
        "quantity_suggested": proposal.quantity_suggested,
        "quantity_unit": proposal.quantity_unit,
        "category_suggested": proposal.category_suggested,
        "is_perishable_suggested": proposal.is_perishable_suggested,
        "bbox_x": proposal.bbox_x,
        "bbox_y": proposal.bbox_y,
        "bbox_w": proposal.bbox_w,
        "bbox_h": proposal.bbox_h,
        "source": proposal.source,
        "state": proposal.state,
    }


def classify_label_hint(label_hint: str) -> dict:
    normalized = normalize_label(label_hint or "manual item")
    category, perishable = suggest_attributes(normalized)
    return {
        "label_raw": label_hint or "manual item",
        "label_normalized": normalized,
        "confidence": 0.2,
        "quantity_suggested": 1.0,
        "quantity_unit": "count",
        "category_suggested": category,
        "is_perishable_suggested": perishable,
        "source": "manual",
        "state": "pending",
    }


def suggest_attributes(normalized_label: str) -> tuple[str, bool]:
    label = normalized_label.lower()
    if any(k in label for k in ["apple", "banana", "orange", "lettuce", "spinach", "tomato"]):
        return ("Produce", True)
    if any(k in label for k in ["milk", "yogurt", "cheese", "egg"]):
        return ("Dairy & Eggs", True)
    if any(k in label for k in ["chicken", "beef", "fish", "salmon", "shrimp"]):
        return ("Meat & Seafood", True)
    if any(k in label for k in ["frozen", "ice cream"]):
        return ("Frozen Foods", True)
    if any(k in label for k in ["soda", "juice", "coffee", "tea", "water"]):
        return ("Beverages", False)
    if any(k in label for k in ["can", "beans", "pasta", "rice", "flour", "sauce"]):
        return ("Pantry", False)
    return ("Other", False)
