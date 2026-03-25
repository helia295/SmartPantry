from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


PRESETS: dict[str, dict[str, Any]] = {
    "smoke-cpu": {
        "epochs": 1,
        "imgsz": 320,
        "batch": 1,
        "device": "cpu",
        "fraction": 0.1,
        "workers": 0,
        "patience": 1,
        "optimizer": "auto",
        "lr0": None,
        "weight_decay": None,
        "mosaic": 0.0,
    },
    "full-cpu": {
        "epochs": 50,
        "imgsz": 640,
        "batch": 1,
        "device": "cpu",
        "fraction": 1.0,
        "workers": 0,
        "patience": 10,
        "optimizer": "auto",
        "lr0": None,
        "weight_decay": None,
        "mosaic": 0.0,
    },
    "full-gpu": {
        "epochs": 50,
        "imgsz": 640,
        "batch": 16,
        "device": "0",
        "fraction": 1.0,
        "workers": 8,
        "patience": 10,
        "optimizer": "auto",
        "lr0": None,
        "weight_decay": None,
        "mosaic": 1.0,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 on the pantry object detection dataset."
    )
    parser.add_argument(
        "--data-yaml",
        required=True,
        help="Path to YOLO-format data.yaml",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default=None,
        help="Apply a recommended training preset before any manual overrides.",
    )
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Base model checkpoint to fine-tune.",
    )
    parser.add_argument("--epochs", type=int, default=None, help="Training epochs.")
    parser.add_argument("--imgsz", type=int, default=None, help="Training image size.")
    parser.add_argument("--batch", type=int, default=None, help="Batch size.")
    parser.add_argument("--device", default=None, help="Training device, e.g. cpu, 0.")
    parser.add_argument(
        "--fraction",
        type=float,
        default=None,
        help="Fraction of dataset to use, from 0 to 1.",
    )
    parser.add_argument("--workers", type=int, default=None, help="Dataloader workers.")
    parser.add_argument("--patience", type=int, default=None, help="Early stopping patience.")
    parser.add_argument(
        "--optimizer",
        default=None,
        help="Ultralytics optimizer setting, e.g. auto, SGD, AdamW.",
    )
    parser.add_argument("--lr0", type=float, default=None, help="Initial learning rate override.")
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=None,
        help="Weight decay override.",
    )
    parser.add_argument(
        "--mosaic",
        type=float,
        default=None,
        help="Mosaic augmentation probability.",
    )
    parser.add_argument(
        "--project",
        default="./runs/pantry-finetune",
        help="Ultralytics project output directory.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Run name. Defaults to preset-based name.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Ask validation to save COCO-style JSON predictions where supported.",
    )
    parser.add_argument(
        "--out-json",
        default="./runs/pantry-finetune/latest_training_summary.json",
        help="Path to write summarized training metadata.",
    )
    return parser.parse_args()


def resolve_args(args: argparse.Namespace, settings) -> argparse.Namespace:
    merged = vars(args).copy()
    if args.preset:
        merged = {**PRESETS[args.preset], **{k: v for k, v in merged.items() if v is not None}}

    if merged.get("imgsz") is None:
        merged["imgsz"] = settings.yolo_inference_size
    if merged.get("device") is None:
        merged["device"] = "cpu"
    if merged.get("fraction") is None:
        merged["fraction"] = 1.0
    if merged.get("workers") is None:
        merged["workers"] = 0
    if merged.get("patience") is None:
        merged["patience"] = 10
    if merged.get("optimizer") is None:
        merged["optimizer"] = "auto"
    if merged.get("epochs") is None:
        merged["epochs"] = 50
    if merged.get("batch") is None:
        merged["batch"] = 16
    if merged.get("name") is None:
        merged["name"] = args.preset or "custom-run"
    return argparse.Namespace(**merged)


def _round(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def main() -> int:
    raw_args = parse_args()
    settings = get_settings()
    args = resolve_args(raw_args, settings)

    data_yaml = Path(raw_args.data_yaml).expanduser().resolve()
    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {data_yaml}")

    project_dir = Path(args.project).expanduser().resolve()
    out_json = Path(raw_args.out_json).expanduser().resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO

    model = YOLO(raw_args.model)
    train_kwargs: dict[str, Any] = {
        "data": str(data_yaml),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "fraction": args.fraction,
        "workers": args.workers,
        "patience": args.patience,
        "optimizer": args.optimizer,
        "project": str(project_dir),
        "name": args.name,
        "mosaic": args.mosaic,
        "pretrained": True,
        "verbose": False,
        "plots": False,
        "save": True,
        "val": True,
    }
    if args.lr0 is not None:
        train_kwargs["lr0"] = args.lr0
    if getattr(args, "weight_decay", None) is not None:
        train_kwargs["weight_decay"] = args.weight_decay

    results = model.train(
        **train_kwargs,
    )

    metrics = getattr(results, "results_dict", {}) or {}
    save_dir = Path(getattr(results, "save_dir", project_dir / args.name))
    best_ckpt = save_dir / "weights" / "best.pt"
    last_ckpt = save_dir / "weights" / "last.pt"

    summary = {
        "model": raw_args.model,
        "dataset": str(data_yaml),
        "preset": raw_args.preset,
        "config": {
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "fraction": args.fraction,
            "workers": args.workers,
            "patience": args.patience,
            "optimizer": args.optimizer,
            "lr0": args.lr0,
            "weight_decay": getattr(args, "weight_decay", None),
            "mosaic": args.mosaic,
        },
        "artifacts": {
            "save_dir": str(save_dir),
            "best_checkpoint": str(best_ckpt),
            "last_checkpoint": str(last_ckpt),
        },
        "metrics": {k: _round(v) for k, v in metrics.items()},
    }

    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("YOLO fine-tuning complete")
    print("-------------------------")
    print(f"Run dir: {save_dir}")
    print(f"Best checkpoint: {best_ckpt}")
    if metrics:
        for key in sorted(metrics):
            print(f"{key}: {_round(metrics[key])}")
    print(f"Summary JSON: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
