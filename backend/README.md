# SmartPantry API

FastAPI backend for SmartPantry. See repo root [README](../README.md) for setup and milestones.

## Detection Eval Script (M4)

Run a quick benchmark on a folder of images:

```bash
cd backend
python scripts/eval_detection.py --images-dir /path/to/images --provider yolo --out-json ./eval_detection_report.json
```
