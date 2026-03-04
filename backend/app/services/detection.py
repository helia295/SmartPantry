from __future__ import annotations

import re
from pathlib import Path


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
