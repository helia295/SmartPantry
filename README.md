# SmartPantry

SmartPantry is an AI-assisted kitchen inventory app built around a human-in-the-loop workflow. Users can upload pantry images, review detection proposals before anything is committed, maintain a structured inventory, and receive recipe recommendations ranked against confirmed pantry state.

## Highlights

- JWT-based auth with registration, login, and automatic post-register sign-in
- Inventory CRUD with per-user scoping
- Image upload with local storage or Cloudflare R2-backed storage
- Detection sessions with YOLO-first inference and mock fallback
- Review flows for grouped proposals, per-box proposals, and manual add/correction
- Explicit confirmation flow before any inventory mutation
- Inventory-aware recipe recommendations with pagination
- Recipe feedback (`like` / `dislike`) and a saved recipe book

## Architecture

```text
Next.js dashboard
  -> FastAPI API
      -> SQLite (MVP app state)
      -> Local storage or Cloudflare R2 (image bytes)
      -> In-process detection service (YOLO or mock fallback)
```

Key design choices:

- Confirmed inventory is the source of truth; model output is always reviewable and never auto-committed.
- Image blobs live in storage, while structured app state lives in the database.
- Recipe ranking is deterministic and explainable.
- SQLite keeps the local MVP simple; PostgreSQL is the intended next database step for real deployment scale.

## Repo Structure

```text
SmartPantry/
├── backend/               FastAPI API, models, services, scripts, tests
├── frontend/              Next.js App Router frontend
├── .github/workflows/     CI configuration
├── .env.example           Shared environment reference
└── README.md
```

Backend layout:

- `app/api/` : route modules
- `app/models/` : SQLAlchemy models
- `app/schemas/` : Pydantic response/request models
- `app/services/` : detection, recipes, and storage logic
- `scripts/` : import and evaluation utilities
- `tests/` : isolated backend test suite

## Implemented Features

### Inventory and Auth

- Register, login, and `/auth/me`
- User-scoped inventory CRUD
- Timezone persistence

### Image Detection Workflow

- Upload up to three pantry images per session
- Detection provider abstraction
- YOLO default with runtime fallback to mock detection
- Grouped review and per-box review
- Manual point-add flow for missed detections
- Confirm/add/update/reject actions that create inventory change logs

### Recipe Workflow

- Recipe import pipeline from a local CSV dataset
- Inventory-aware recommendation ranking
- Main-ingredient prioritization
- Ingredient canonicalization / synonym handling
- Paginated recommendation results
- Recipe detail page
- Like/dislike feedback
- Saved recipe book page

## Dataset Attribution

Recipe recommendations currently use a locally imported Kaggle dataset:

- Dataset: `manjushwarkhairkar/all-recipe-dataset`
- Source described by the dataset author as scraped from Allrecipes.com
- License listed on Kaggle: MIT

This dataset is not stored in git. The expected workflow is:

- download the CSV locally outside the repo
- run the backend import script
- keep only the normalized application data in the local database

Example import command:

```bash
cd backend
source .venv/bin/activate
python scripts/import_recipes.py \
  --input-csv "/absolute/path/to/All_Recipe_Web_Scraping_Dataset.csv"
```

Current UX note:

- the dataset does not provide a reliable canonical recipe URL per row
- the frontend therefore uses a best-effort `Search on Allrecipes` link instead of claiming to deep-link directly to a source recipe page

## Tooling

- Node.js: `20.20.1` via `[.nvmrc](.nvmrc)`
- Python: `>=3.10`

If you use `nvm`:

```bash
nvm use
node -v
npm -v
```

Next.js 14 requires Node `>=18.17.0`. Using mixed Node versions across shells can break `npm install`, `next dev`, and `next build`.

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml]"
uvicorn app.main:app --reload --port 8000
```

Backend endpoints:

- API root: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
nvm use
npm ci
npm run dev
```

Frontend app:

- `http://localhost:3000`

If port `3000` is already occupied by another local tool, either free that port or run Next on another port temporarily.

## Environment Variables

See `[.env.example](.env.example)` for the shared baseline.

Common backend settings:

- `DATABASE_URL`
- `JWT_SECRET`
- `DETECTION_PROVIDER`
- `YOLO_MODEL_NAME`
- `STORAGE_PROVIDER`
- `LOCAL_STORAGE_DIR`
- `R2_*` credentials

Frontend:

- `NEXT_PUBLIC_API_URL`

## Testing

Backend tests are run with pytest and use an isolated temporary SQLite database so test cleanup does not mutate the local development database.

Common backend test command:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_recipes.py tests/test_recipe_import.py tests/test_auth.py tests/test_inventory.py -q
```

Frontend verification:

```bash
cd frontend
npm run build
```

CI currently runs:

- backend tests
- frontend lint
- frontend build

## Milestone Status

1. `M1` Scaffold and hello world: complete
2. `M2` Auth and inventory foundation: complete
3. `M3` Image upload and detection sessions: complete
4. `M4` Detection review UX: complete
5. `M5` Human-in-the-loop inventory confirmation: complete
6. `M6` Recipe recommendations and recipe feedback flow: complete
7. `M7` Deployment hardening: in progress
8. `M8` Performance, limits, and polish: planned

## Known Limits

- SQLite is the current local/MVP database, not the intended long-term production database
- image retention cleanup is not automated yet
- no formal migration system yet
- no rate limiting yet
- recipe recommendations are deterministic and local-rule-based

## License

See [LICENSE](LICENSE).