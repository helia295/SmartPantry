from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.detection import run_detection

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SmartPantry detection benchmark on a folder of images"
    )
    parser.add_argument("--images-dir", required=True, help="Directory containing test images")
    parser.add_argument(
        "--provider",
        choices=["mock", "yolo"],
        default=None,
        help="Override DETECTION_PROVIDER for this run",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=None,
        help="Override DETECTION_CONFIDENCE_THRESHOLD for this run",
    )
    parser.add_argument(
        "--out-json",
        default="./eval_detection_report.json",
        help="Path to write JSON report",
    )
    return parser.parse_args()


def collect_images(images_dir: Path) -> list[Path]:
    if not images_dir.exists() or not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    images = [
        p
        for p in sorted(images_dir.iterdir())
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    if not images:
        raise ValueError(f"No supported image files found in: {images_dir}")
    return images


def summarize(latencies_ms: list[float], num_proposals: list[int]) -> dict[str, Any]:
    p50 = statistics.median(latencies_ms)
    if len(latencies_ms) >= 2:
        p95 = statistics.quantiles(latencies_ms, n=20)[18]
    else:
        p95 = latencies_ms[0]

    return {
        "num_images": len(latencies_ms),
        "avg_latency_ms": round(statistics.mean(latencies_ms), 2),
        "p50_latency_ms": round(p50, 2),
        "p95_latency_ms": round(p95, 2),
        "avg_proposals_per_image": round(statistics.mean(num_proposals), 2),
    }


def main() -> None:
    args = parse_args()
    settings = get_settings()

    if args.provider is not None:
        settings.detection_provider = args.provider
    if args.conf is not None:
        settings.detection_confidence_threshold = args.conf

    images_dir = Path(args.images_dir).resolve()
    out_json = Path(args.out_json).resolve()
    files = collect_images(images_dir)

    rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    proposal_counts: list[int] = []

    for image_path in files:
        image_bytes = image_path.read_bytes()
        start = time.perf_counter()
        proposals, model_version = run_detection(
            image_bytes=image_bytes,
            original_filename=image_path.name,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        latencies_ms.append(elapsed_ms)
        proposal_counts.append(len(proposals))

        rows.append(
            {
                "filename": image_path.name,
                "model_version": model_version,
                "latency_ms": round(elapsed_ms, 2),
                "num_proposals": len(proposals),
                "labels": [p.get("label_normalized", "") for p in proposals],
                "confidences": [round(float(p.get("confidence") or 0.0), 4) for p in proposals],
            }
        )

    report = {
        "settings": {
            "provider": settings.detection_provider,
            "confidence_threshold": settings.detection_confidence_threshold,
            "yolo_model_name": settings.yolo_model_name,
        },
        "summary": summarize(latencies_ms, proposal_counts),
        "results": rows,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Detection eval complete")
    print(f"Images: {report['summary']['num_images']}")
    print(f"Avg latency: {report['summary']['avg_latency_ms']} ms")
    print(f"P50/P95 latency: {report['summary']['p50_latency_ms']} / {report['summary']['p95_latency_ms']} ms")
    print(f"Avg proposals/image: {report['summary']['avg_proposals_per_image']}")
    print(f"Report: {out_json}")


if __name__ == "__main__":
    main()
