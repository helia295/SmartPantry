# SmartPantry API

FastAPI backend for SmartPantry. The backend owns authentication, inventory state, image upload and detection workflows, recipe recommendation APIs, and storage abstraction.

For the higher-level product overview, see the repo root [README](../README.md).

## Backend Responsibilities

- user registration, login, and identity lookup
- inventory CRUD and change logs
- image upload, image metadata, and image content retrieval
- detection session persistence and proposal review support
- recipe import, recommendation ranking, feedback, and saved recipe book APIs
- storage abstraction for local filesystem and Cloudflare R2

## App Structure

```text
backend/
├── app/
│   ├── api/         FastAPI routers
│   ├── core/        config and security
│   ├── models/      SQLAlchemy models
│   ├── schemas/     Pydantic schemas
│   ├── services/    storage, detection, recipe logic
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

Docs:

- `http://localhost:8000/docs`

## Environment Variables

Most backend settings are read from `backend/.env` or exported shell variables.

Core settings:

- `DATABASE_URL` : defaults to local SQLite `sqlite:///./smartpantry.db`
- `JWT_SECRET` : must be overridden for any non-local deployment
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`

Upload and detection:

- `MAX_UPLOAD_IMAGES`
- `MAX_IMAGE_SIZE_MB`
- `IMAGE_RETENTION_DAYS`
- `DETECTION_PROVIDER`
- `YOLO_MODEL_NAME`
- `DETECTION_CONFIDENCE_THRESHOLD`

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

## Storage Modes

### Local storage

Good for development:

- image bytes are stored under `backend/storage/`
- structured metadata stays in SQLite

### Cloudflare R2

Supported for deployment-oriented storage:

- image bytes are stored in R2
- structured metadata still stays in the database

This separation is intentional:

- object storage is for blobs/files
- the database is for structured relational state

## Detection Modes

### `yolo`

- preferred local/demo detection provider
- CPU inference path
- falls back to mock if inference or dependencies fail at runtime

### `mock`

- deterministic development/CI fallback
- useful when ML dependencies are unavailable

Detection evaluation script:

```bash
cd backend
python scripts/eval_detection.py --images-dir /path/to/images --provider yolo --out-json ./eval_detection_report.json
```

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

Current recipe routes:

- `GET /recipes/recommendations`
- `GET /recipes/{id}`
- `POST /recipes/{id}/feedback`
- `GET /recipes/book`

Current behavior:

- recommendations are ranked against confirmed inventory
- main ingredients (if user inputed) are prioritized ahead of other inventory-only matches
- dislikes are excluded from future recommendation pages
- likes are saved to the recipe book

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
- no background cleanup job for expired images yet
- startup still uses MVP-style auto-create rather than a production migration path
- deployment CORS/secret handling docs are still being expanded in Milestone 7

