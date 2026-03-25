from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the current YOLO model on a YOLO-format dataset split."
    )
    parser.add_argument(
        "--data-yaml",
        required=True,
        help="Path to the dataset data.yaml file",
    )
    parser.add_argument(
        "--split",
        default="test",
        choices=["train", "val", "test"],
        help="Dataset split to evaluate",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="YOLO model path/name to evaluate. Defaults to backend config.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=None,
        help="Inference image size. Defaults to backend config.",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=None,
        help="Confidence threshold. Defaults to backend config.",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.6,
        help="IoU threshold to use during validation",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Ultralytics device string, e.g. cpu, 0, 0,1",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=1,
        help="Validation batch size. Use 1 for CPU unless you know you have room.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Dataloader workers. 0 is the safest cross-platform default.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Ask Ultralytics to save COCO-style JSON predictions where supported.",
    )
    parser.add_argument(
        "--out-json",
        default="./benchmark_yolo_accuracy_report.json",
        help="Path to write the summarized metrics report",
    )
    return parser.parse_args()


def _round(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _extract_scalar_metric(primary: Any, *fallbacks: Any) -> float | None:
    candidates = (primary, *fallbacks)
    for value in candidates:
        rounded = _round(value)
        if rounded is not None:
            return rounded
    return None


def summarize_metrics(metrics: Any, args: argparse.Namespace, model_name: str, data_yaml: Path) -> dict[str, Any]:
    box = getattr(metrics, "box", None)
    speed = getattr(metrics, "speed", None) or {}
    results_dict = getattr(metrics, "results_dict", None) or {}

    class_names: dict[int, str] = {}
    names_raw = getattr(metrics, "names", None)
    if isinstance(names_raw, dict):
        class_names = {int(k): str(v) for k, v in names_raw.items()}
    elif isinstance(names_raw, list):
        class_names = {idx: str(name) for idx, name in enumerate(names_raw)}

    per_class_map50 = {}
    maps = getattr(box, "maps", None)
    if maps is not None:
        try:
            for idx, value in enumerate(maps):
                per_class_map50[str(class_names.get(idx, idx))] = _round(value)
        except TypeError:
            pass

    return {
        "model": {
            "model_name": model_name,
            "device": args.device,
            "imgsz": args.imgsz,
            "conf": args.conf,
            "iou": args.iou,
            "batch": args.batch,
            "workers": args.workers,
        },
        "dataset": {
            "data_yaml": str(data_yaml),
            "split": args.split,
        },
        "metrics": {
            "precision": _extract_scalar_metric(
                getattr(box, "mp", None),
                results_dict.get("metrics/precision(B)"),
                getattr(box, "p", None),
            ),
            "recall": _extract_scalar_metric(
                getattr(box, "mr", None),
                results_dict.get("metrics/recall(B)"),
                getattr(box, "r", None),
            ),
            "map50": _extract_scalar_metric(
                getattr(box, "map50", None),
                results_dict.get("metrics/mAP50(B)"),
            ),
            "map50_95": _extract_scalar_metric(
                getattr(box, "map", None),
                results_dict.get("metrics/mAP50-95(B)"),
            ),
            "fitness": _extract_scalar_metric(
                getattr(metrics, "fitness", None),
                results_dict.get("fitness"),
            ),
        },
        "speed_ms_per_image": {
            key: _round(value, digits=2)
            for key, value in speed.items()
        },
        "per_class_map": per_class_map50,
        "results_dir": str(getattr(metrics, "save_dir", "")),
    }


def print_summary(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    speed = report["speed_ms_per_image"]
    print("YOLO evaluation complete")
    print("------------------------")
    print(f"Model: {report['model']['model_name']}")
    print(f"Dataset: {report['dataset']['data_yaml']}")
    print(f"Split: {report['dataset']['split']}")
    print(f"Precision: {metrics['precision']}")
    print(f"Recall: {metrics['recall']}")
    print(f"mAP@50: {metrics['map50']}")
    print(f"mAP@50-95: {metrics['map50_95']}")
    if speed:
        speed_bits = ", ".join(f"{k}={v} ms" for k, v in speed.items())
        print(f"Speed: {speed_bits}")
    print(f"Report: {report['results_dir']}")


def main() -> int:
    args = parse_args()
    settings = get_settings()

    data_yaml = Path(args.data_yaml).expanduser().resolve()
    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {data_yaml}")

    model_name = args.model or settings.yolo_model_name
    imgsz = args.imgsz or settings.yolo_inference_size
    conf = args.conf if args.conf is not None else settings.detection_confidence_threshold

    from ultralytics import YOLO

    model = YOLO(model_name)
    metrics = model.val(
        data=str(data_yaml),
        split=args.split,
        imgsz=imgsz,
        conf=conf,
        iou=args.iou,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        verbose=False,
        plots=False,
        save_json=args.save_json,
    )

    report = summarize_metrics(
        metrics=metrics,
        args=argparse.Namespace(**{**vars(args), "imgsz": imgsz, "conf": conf}),
        model_name=model_name,
        data_yaml=data_yaml,
    )

    out_json = Path(args.out_json).expanduser().resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
