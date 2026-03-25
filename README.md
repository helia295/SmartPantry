# SmartPantry

SmartPantry is a full-stack, AI-assisted kitchen inventory app built around a human-in-the-loop workflow. Users can upload pantry or fridge photos, review detection proposals before anything is saved, maintain a structured inventory, and discover recipes ranked against confirmed pantry state.

## Highlights

- Account system with registration, login, display names, timezone support, account editing, and inactivity-aware session refresh
- Inventory CRUD with inline editing, category grouping, quick add, and AI-assisted Smart Add
- Cloud-backed image storage with Cloudflare R2
- YOLO-based detection with explicit user review before inventory changes are persisted
- Grouped review, per-box review, and manual point-add for missed detections
- Recent upload history with thumbnail previews and retention cleanup
- Inventory-aware recipe recommendations with feedback, favorites, and reusable hashtags
- Pantry follow-through flow that lets users review inventory changes after cooking

## Current Architecture

```text
Next.js frontend on Vercel
  -> Vercel server-side proxy route
      -> FastAPI backend on AWS EC2 (Docker + Nginx)
          -> Neon PostgreSQL
          -> Cloudflare R2 for uploaded image blobs
          -> In-process YOLO detection on CPU
```

Key design choices:

- Confirmed inventory is the source of truth. Detection proposals are always reviewable and never auto-committed.
- The frontend stays on Vercel, but browser requests go through a same-origin proxy route instead of calling the EC2 backend directly.
- Structured application state lives in the database, while uploaded image bytes live in object storage.
- Recipe ranking is deterministic and explainable.
- Recipe follow-through is conservative and user-reviewed instead of silently inferred.

## Tech Stack

- Frontend: Next.js 14, React 18
- Backend: FastAPI, SQLAlchemy, Pydantic
- Detection: Ultralytics YOLO
- Database: Neon PostgreSQL
- Storage: Cloudflare R2
- Deployment: Vercel + AWS EC2 + Nginx + Docker

## Repo Structure

```text
SmartPantry/
├── backend/               FastAPI API, models, services, scripts, tests
├── frontend/              Next.js App Router frontend
├── docs/                  Private architecture/interview/deployment notes
├── .github/workflows/     CI configuration
├── .env.example           Shared environment reference
└── README.md
```

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml]"
uvicorn app.main:app --reload --port 8000
```

Backend:

- API root: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
nvm use
npm ci
npm run dev
```

Frontend:

- `http://localhost:3000`

## Environment Variables

See [.env.example](.env.example) for the shared baseline.

Backend settings commonly needed in deployment:

- `APP_ENV`
- `DATABASE_URL`
- `JWT_SECRET`
- `CORS_ORIGINS`
- `STORAGE_PROVIDER`
- `R2_*`
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
- `YOLO_INFERENCE_SIZE`
- `YOLO_MAX_IMAGE_DIM`

Frontend:

- `API_PROXY_TARGET` for deployed Vercel server-side proxying
- `NEXT_PUBLIC_API_URL` for local frontend-to-backend development when needed

## Testing

Backend tests:

```bash
cd backend
./.venv/bin/python -m pytest -q
```

Frontend verification:

```bash
cd frontend
npm run build
```

## Dataset Attribution

Recipe recommendations currently use a locally imported Kaggle dataset:

- Dataset: `manjushwarkhairkar/all-recipe-dataset`
- Dataset description indicates the rows were scraped from Allrecipes.com
- Kaggle lists the dataset license as MIT

The raw CSV is not stored in git. The expected workflow is:

- download the CSV locally outside the repo
- run the backend import script
- keep normalized application data in the database

Example import command:

```bash
cd backend
source .venv/bin/activate
python scripts/import_recipes.py \
  --input-csv "/absolute/path/to/All_Recipe_Web_Scraping_Dataset.csv"
```

## Known Limits

- Detection still runs inline on CPU rather than through a dedicated background worker
- Alembic is configured and the current production schema is stamped to the baseline revision, but deployment still keeps startup table creation enabled until the migration-first rollout is fully enforced
- Current rate limiting is in-memory and single-instance rather than distributed
- Recipe recommendations are deterministic and rules-based rather than personalized by a learned ranking model
- The deployed backend currently uses an EC2 public IP plus Vercel proxying rather than a custom backend domain

## License

See [LICENSE](LICENSE).
