# SmartPantry API

FastAPI backend for SmartPantry. The backend owns authentication, inventory state, image upload and review workflows, recipe recommendation APIs, storage abstraction, and scheduled retention cleanup for uploaded images.

For the product-level overview, see the repo root [README](../README.md).

## Responsibilities

- registration, login, token refresh, and identity lookup
- profile, password, and timezone updates
- inventory CRUD and change logs
- image upload, image metadata, and image content retrieval
- detection session persistence and proposal review support
- recipe import, recommendation ranking, feedback, favorites, hashtags, and pantry follow-through APIs
- OpenAI-backed pantry assistant generation over grounded recipe candidates
- storage abstraction for local filesystem and Cloudflare R2
- startup and recurring cleanup of expired uploaded images
- pantry-specific YOLO checkpoint loading and detection warmup

## Backend Structure

```text
backend/
├── app/
│   ├── api/         FastAPI routers
│   ├── core/        config and security
│   ├── models/      SQLAlchemy models
│   ├── schemas/     Pydantic schemas
│   ├── services/    storage, detection, image retention, recipe logic
│   ├── db.py        engine/session setup
│   └── main.py      app startup and router wiring
├── scripts/         import and evaluation scripts
└── tests/           isolated backend tests
```

## Local Setup

Requirements:

- Python `>=3.10`
- virtualenv recommended

Install:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml]"
```

Run locally:

```bash
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs:

- `http://localhost:8000/docs`

## Docker

Build locally:

```bash
cd backend
docker build -t smartpantry-backend .
```

Run locally:

```bash
docker run --rm -p 8000:8000 --env-file .env smartpantry-backend
```

## Environment Variables

Most backend settings are loaded from `backend/.env` or exported shell variables.

Core settings:

- `APP_ENV`
- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`

Upload and detection:

- `MAX_UPLOAD_IMAGES`
- `MAX_IMAGE_SIZE_MB`
- `IMAGE_RETENTION_DAYS`
- `IMAGE_CLEANUP_INTERVAL_MINUTES`
- `IMAGE_CLEANUP_BATCH_LIMIT`
- `AUTH_RATE_LIMIT_REQUESTS`
- `AUTH_RATE_LIMIT_WINDOW_SECONDS`
- `REGISTER_RATE_LIMIT_REQUESTS`
- `REGISTER_RATE_LIMIT_WINDOW_SECONDS`
- `IMAGE_UPLOAD_RATE_LIMIT_REQUESTS`
- `IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`
- `DETECTION_PROVIDER`
- `YOLO_MODEL_NAME`
- `DETECTION_CONFIDENCE_THRESHOLD`
- `YOLO_INFERENCE_SIZE`
- `YOLO_MAX_IMAGE_DIM`

Storage:

- `STORAGE_PROVIDER`
- `LOCAL_STORAGE_DIR`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `CF_ACCOUNT_ID`

Pantry assistant:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_ASSISTANT_ENABLED`
- `OPENAI_ASSISTANT_TIMEOUT_SECONDS`
- `OPENAI_ASSISTANT_MAX_RECIPES`
- `OPENAI_ASSISTANT_MAX_PANTRY_ITEMS`

## Data and Storage Model

The backend intentionally separates:

- relational application state in the database
- uploaded image bytes in blob/object storage

Current deployment-oriented storage choice:

- `STORAGE_PROVIDER=r2`
- image bytes in Cloudflare R2
- metadata and detection session state in PostgreSQL

Retention behavior:

- expired image cleanup runs on startup
- recurring cleanup runs in-process on an interval
- image routes also perform opportunistic cleanup as a fallback

Rate limiting behavior:

- login, registration, and image upload routes are protected by a lightweight in-memory limiter
- this is appropriate for the current single-instance deployment
- a distributed limiter backed by Redis or another shared store would be the next step if the app ever runs across multiple backend instances

## Detection Modes

### `yolo`

- primary detection mode for real AI-assisted review
- downsizes oversized uploads before inference
- warms the detection backend on startup to avoid first-request surprises
- production currently points `YOLO_MODEL_NAME` at a pantry-finetuned YOLOv8n checkpoint mounted into the container from the EC2 host

### `mock`

- deterministic fallback for development, CI, or low-resource environments

Deployment note:

- small free-tier PaaS instances (Render) were not sufficient for the current YOLO CPU workload
- the backend now targets a host with more RAM (AWS EC2)
- generic `yolov8n.pt` baseline quality on the held-out pantry test set was poor (`0.020` mAP@50, `0.018` mAP@50-95)
- pantry-domain fine-tuning improved the same test set to `0.472` mAP@50 and `0.361` mAP@50-95
- after deploying the fine-tuned checkpoint, Smart Add latency improved to `689.9 ms` p50 / `752.7 ms` p95 on the public Vercel path and `584.7 ms` p50 / `665.6 ms` p95 on the direct backend path

## Pantry Assistant Design

The pantry assistant is intentionally layered on top of the existing deterministic recipe ranking flow instead of replacing it.

The backend flow is:

1. load confirmed pantry inventory
2. rank recipe candidates with the existing `recommend_recipes()` service
3. include pantry-age signals such as perishable status and older perishables in stock
4. optionally boost user-selected pantry ingredients and optional age-based prioritization choices
5. send only the top candidate recipes plus compact pantry context to the OpenAI API
6. return structured JSON that the frontend can render directly

Why this design:

- keeps the assistant grounded in real pantry state and known recipes
- avoids inventing new recipes or mutating application state
- keeps cost and latency lower than sending the entire recipe corpus
- makes the assistant easier to test because the route contract is structured JSON

## Recipe API Surface

Current routes include:

- `POST /recipes/assistant/use-up`
- `GET /recipes/recommendations`
- `GET /recipes/{id}`
- `POST /recipes/{id}/feedback`
- `DELETE /recipes/{id}/feedback`
- `GET /recipes/book`
- `PUT /recipes/{id}/tags`
- `POST /recipes/{id}/cook-preview`
- `POST /recipes/{id}/cook-apply`

Behavior:

- the pantry assistant is advisory only and never writes inventory state
- older perishable pantry items can be surfaced as an explicit prioritization signal to the assistant
- users can also explicitly prioritize specific pantry ingredients from the UI, and those ingredients are used both for candidate ranking bias and assistant guidance
- recommendations are ranked against confirmed inventory
- dislikes are excluded from future recommendation pages
- likes are saved to the favorite recipe book
- hashtags organize favorites without introducing heavier collection management
- pantry follow-through remains conservative and explicitly reviewed

## Deployment Posture

Current deployed backend target:

- AWS EC2
- Ubuntu LTS
- Dockerized FastAPI app
- Nginx reverse proxy on port 80
- Neon PostgreSQL
- Cloudflare R2
- Vercel frontend calling the backend through a same-origin proxy route

Why this deployment shape:

- keeps the FastAPI + YOLO architecture largely unchanged
- gives the YOLO runtime more memory than low-memory free PaaS offerings
- keeps frontend deployment simple on Vercel
- avoids exposing backend secrets to the browser
- allows the backend to mount a host-side model artifact into `/app/models` without baking large binaries into git

## Testing

Run backend tests:

```bash
cd backend
./.venv/bin/python -m pytest -q
```

Important note:

- pytest uses an isolated temporary database and temp storage paths
- tests do not mutate the local development database

## Current Hardening Gaps

- Alembic is configured and the current production schema is stamped to the baseline revision, but startup `create_all()` is still enabled until deployment is tightened around `alembic upgrade head`
- current rate limiting is in-memory rather than distributed
- no custom backend domain yet
- detection still runs inline rather than via a dedicated worker or queue
