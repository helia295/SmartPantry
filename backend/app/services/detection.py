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
    return {
        "label_raw": label_raw,
        "label_normalized": normalize_label(label_raw),
        "confidence": 0.35,
        "quantity_suggested": 1.0,
        "quantity_unit": "count",
        "state": "pending",
    }
