from __future__ import annotations

import io
import logging
import re
from functools import lru_cache
from pathlib import Path

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
    from ultralytics import YOLO

    return YOLO(model_name)


def run_yolo_detection(image_bytes: bytes, confidence_threshold: float, model_name: str) -> list[dict]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for YOLO inference") from exc

    model = _load_yolo_model(model_name)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    if width <= 0 or height <= 0:
        return []

    results = model.predict(source=image, conf=confidence_threshold, verbose=False, device="cpu")
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
