# SmartPantry API

FastAPI backend for SmartPantry. The backend owns authentication, inventory state, image upload and review workflows, recipe recommendation APIs, storage abstraction, and scheduled retention cleanup for uploaded images.

For the higher-level product overview, see the repo root [README](../README.md).

## Backend Responsibilities

- user registration, login, token refresh, and identity lookup
- account profile, password, and timezone updates
- inventory CRUD and change logs
- image upload, image metadata, and image content retrieval
- detection session persistence and proposal review support
- recipe import, recommendation ranking, feedback, favorites, hashtagging, and pantry follow-through APIs
- storage abstraction for local filesystem and Cloudflare R2
- scheduled cleanup of expired uploaded images

## App Structure

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

## Requirements

- Python `>=3.10`
- virtualenv recommended

Setup:

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

Build container locally:

```bash
cd backend
docker build -t smartpantry-backend .
docker run --rm -p 8000:8000 --env-file .env smartpantry-backend
```

Docs:

- `http://localhost:8000/docs`

## Environment Variables

Most backend settings are read from `backend/.env` or exported shell variables.

Core settings:

- `APP_ENV` : `development` locally, `production` in deployed environments
- `DATABASE_URL` : defaults to local SQLite `sqlite:///./smartpantry.db`
- `JWT_SECRET` : must be overridden for any non-local deployment
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS` : comma-separated list of trusted frontend origins

Upload and detection:

- `MAX_UPLOAD_IMAGES`
- `MAX_IMAGE_SIZE_MB`
- `IMAGE_RETENTION_DAYS`
- `IMAGE_CLEANUP_INTERVAL_MINUTES`
- `IMAGE_CLEANUP_BATCH_LIMIT`
- `DETECTION_PROVIDER`
- `YOLO_MODEL_NAME`
- `DETECTION_CONFIDENCE_THRESHOLD`
- `YOLO_INFERENCE_SIZE`
- `YOLO_MAX_IMAGE_DIM`

Storage:

- `STORAGE_PROVIDER` = `local` or `r2`
- `LOCAL_STORAGE_DIR`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

## Database Notes

The local development database is SQLite:

- file: `backend/smartpantry.db`

Why SQLite now:

- zero external setup
- simple local development
- fast enough for MVP and demo use

Planned next step:

- move to PostgreSQL for production deployment and stronger concurrency

The backend currently creates tables automatically on startup for MVP simplicity. Formal migrations are still a future hardening step.

## Deployment Posture

Current local-development defaults are intentionally easy to run, but they are not the intended production posture.

Development-friendly defaults:

- `APP_ENV=development`
- SQLite
- local storage
- development JWT fallback secret
- localhost CORS defaults

Production-oriented target:

- `APP_ENV=production`
- PostgreSQL
- strong `JWT_SECRET`
- explicit deployed frontend origins in `CORS_ORIGINS`
- `STORAGE_PROVIDER=r2` or another object-storage-backed option

Current recommended cloud deployment target:

- Vercel for the frontend
- AWS EC2 for the backend and YOLO inference
- Neon for PostgreSQL
- Cloudflare R2 for uploaded image storage

Why EC2 for the backend:

- keeps the current FastAPI + YOLO architecture mostly unchanged
- gives more control over RAM/CPU than low-memory free PaaS offerings
- supports a stronger conventional backend deployment story than a demo-oriented ML host
- works well with a simple Docker-based deployment flow

The backend emits warnings at startup when clearly unsafe production-like settings are still in use.

## Storage Modes

### Local storage

Good for development:

- image bytes are stored under `backend/storage/`
- structured metadata stays in SQLite

### Cloudflare R2

Supported for deployment-oriented storage:

- image bytes are stored in R2
- structured metadata stays in the database

This separation is intentional:

- object storage is for blobs and files
- the database is for structured relational state

Retention note:

- `IMAGE_RETENTION_DAYS` defines the intended retention policy
- the backend performs a startup sweep and recurring background cleanup for expired images
- image routes still run opportunistic cleanup as a second line of defense
- bucket lifecycle rules can still help on the storage side, especially for Cloudflare R2 deployments

## Detection Modes

### `yolo`

- preferred local/demo detection provider
- CPU inference path
- downsizes oversized uploads before inference to keep phone photos more manageable
- falls back to mock if inference or dependencies fail at runtime

### `mock`

- deterministic development and CI fallback
- useful when ML dependencies are unavailable

Detection evaluation script:

```bash
cd backend
python scripts/eval_detection.py --images-dir /path/to/images --provider yolo --out-json ./eval_detection_report.json
```

Latency tuning:

- `YOLO_MAX_IMAGE_DIM` caps how large an uploaded image stays before YOLO sees it
- `YOLO_INFERENCE_SIZE` controls the model prediction size passed into YOLO
- lower values are usually faster on CPU, but can trade away some small-object accuracy

Deployment note:

- low-memory hosts such as small free-tier PaaS instances may still be too constrained for full YOLO inference
- the current production direction is to run the backend on a host with more RAM rather than redesign the Smart Add flow immediately

## Recipe Import

Recipes are imported from a local CSV file outside the repo.

Current expected dataset:

- Kaggle `manjushwarkhairkar/all-recipe-dataset`

Import command:

```bash
cd backend
source .venv/bin/activate
python scripts/import_recipes.py \
  --input-csv "/absolute/path/to/All_Recipe_Web_Scraping_Dataset.csv"
```

What the importer does:

- parses recipe metadata
- splits ingredient strings
- normalizes ingredient names
- stores normalized rows for recommendation matching

## Recipe API Surface

Current recipe routes include:

- `GET /recipes/recommendations`
- `GET /recipes/{id}`
- `POST /recipes/{id}/feedback`
- `DELETE /recipes/{id}/feedback`
- `GET /recipes/book`
- `PUT /recipes/{id}/tags`
- `POST /recipes/{id}/cook-preview`
- `POST /recipes/{id}/cook-apply`

Current behavior:

- recommendations are ranked against confirmed inventory
- main ingredients are prioritized ahead of other inventory-only matches
- dislikes are excluded from future recommendation pages
- likes are saved to the favorite recipe book
- hashtags are optional organization metadata inside the recipe book
- pantry follow-through is conservative and requires explicit user review before inventory changes are applied

## Testing

Run backend tests:

```bash
cd backend
./.venv/bin/python -m pytest -q
```

Important test note:

- pytest uses an isolated temporary SQLite database
- test cleanup does not touch the local development database

That isolation is intentional because recipe import and integration tests are destructive by design within the test environment.

## Current Hardening Gaps

- no formal migration framework yet
- no rate limiting yet
- startup still uses auto-create rather than a formal production migration path
- PostgreSQL deployment path is documented but not yet implemented in-repo
- detection still runs inline rather than via a dedicated background worker
