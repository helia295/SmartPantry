# SmartPantry

SmartPantry is an AI-assisted kitchen inventory app built around a human-in-the-loop workflow. Users can upload pantry or fridge photos, review detection proposals before anything is saved, keep a structured inventory up to date, and discover recipes ranked against confirmed pantry state.

## Product Highlights

- JWT-based auth with registration, login, display names, account editing, timezone support, and inactivity-based session refresh
- Inventory CRUD with inline editing, category grouping, quick add, and AI-assisted Smart Add
- Image upload with local storage or Cloudflare R2-backed storage
- Detection sessions with YOLO-first inference and mock fallback
- Review flows for grouped proposals, per-box proposals, and manual add/correction
- Recent upload history with thumbnail previews and lazy review loading
- Explicit confirmation flow before any inventory mutation
- Inventory-aware recipe recommendations with pagination
- Recipe feedback (`like` / `dislike`), favorite recipe book, optional hashtags, and recipe detail pages
- Pantry follow-through flow that lets users review inventory changes after cooking a recipe

## Architecture

```text
Next.js frontend
  -> FastAPI API
      -> SQLite (current MVP app state)
      -> Local storage or Cloudflare R2 (image bytes)
      -> In-process detection service (YOLO or mock fallback)
```

Key design choices:

- Confirmed inventory is the source of truth. Model output is always reviewable and never auto-committed.
- Image blobs live in storage, while structured app state lives in the database.
- Recipe ranking is deterministic and explainable rather than LLM-first.
- SQLite keeps local development simple; PostgreSQL is the intended next database step for deployed scale.
- Pantry updates after cooking are conservative and user-reviewed rather than silently inferred.

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
- `app/schemas/` : Pydantic request/response models
- `app/services/` : storage, detection, image retention, and recipe logic
- `scripts/` : import and evaluation utilities
- `tests/` : isolated backend test suite

## Implemented Features

### Auth and Account

- Register, login, and `/auth/me`
- Automatic sign-in immediately after registration
- Display names and dedicated account page
- Profile, email, password, and timezone updates
- Sliding inactivity-based session behavior

### Inventory Workflow

- User-scoped inventory CRUD
- Category tabs with grouped inventory cards
- Quick Add for manual entry
- Smart Add to jump directly into the camera-assisted flow
- Inline item editing, including category, unit, perishable flag, and date refresh
- Inventory change logs

### Image Detection Workflow

- Upload up to three pantry images per request
- Detection provider abstraction
- YOLO default with runtime fallback to mock detection
- Image downscaling before inference for better CPU latency
- Grouped review and per-box review
- Manual point-add flow for missed detections
- Recent upload history with 7-day retention
- Explicit add, update, skip, and manual-proposal review actions
- Dedicated backend image retention cleanup plus route-level cleanup fallback

### Recipe Workflow

- Recipe import pipeline from a local CSV dataset
- Inventory-aware recommendation ranking
- Main-ingredient prioritization
- Ingredient canonicalization and synonym handling
- Paginated recommendation results
- Recipe detail page
- Like/dislike feedback
- Favorite recipe book with optional reusable hashtags
- Pantry follow-through flow to review inventory changes after cooking

## Dataset Attribution

Recipe recommendations currently use a locally imported Kaggle dataset:

- Dataset: `manjushwarkhairkar/all-recipe-dataset`
- Dataset description indicates the rows were scraped from Allrecipes.com
- License listed on Kaggle: MIT

This dataset is not stored in git. The expected workflow is:

- download the CSV locally outside the repo
- run the backend import script
- keep only normalized application data in the database

Example import command:

```bash
cd backend
source .venv/bin/activate
python scripts/import_recipes.py \
  --input-csv "/absolute/path/to/All_Recipe_Web_Scraping_Dataset.csv"
```

Current UX note:

- the dataset does not provide a reliable canonical source URL per row
- the frontend therefore uses a best-effort `Search on Allrecipes` link rather than claiming to deep-link directly to a source recipe page

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

## Environment Variables

See `[.env.example](.env.example)` for the shared baseline.

Common backend settings:

- `APP_ENV`
- `DATABASE_URL`
- `JWT_SECRET`
- `CORS_ORIGINS`
- `DETECTION_PROVIDER`
- `YOLO_MODEL_NAME`
- `YOLO_INFERENCE_SIZE`
- `YOLO_MAX_IMAGE_DIM`
- `STORAGE_PROVIDER`
- `LOCAL_STORAGE_DIR`
- `R2_*` credentials
- `IMAGE_RETENTION_DAYS`
- `IMAGE_CLEANUP_INTERVAL_MINUTES`
- `IMAGE_CLEANUP_BATCH_LIMIT`

Frontend:

- `NEXT_PUBLIC_API_URL`

## Testing

Backend tests use an isolated temporary SQLite database so test cleanup does not mutate the local development database.

Common backend test command:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_auth.py tests/test_inventory.py tests/test_images.py tests/test_recipe_import.py tests/test_recipes.py -q
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
7. `M7` Deployment hardening: complete
8. `M8` Performance, workflow polish, and UI refinement: complete

## Known Limits

- SQLite is still the local/MVP database rather than the intended production database
- no formal migration system yet
- no rate limiting yet
- recipe recommendations are deterministic and local-rule-based rather than personalized by a learned model
- detection still runs in-process on CPU; a background worker or stronger inference target would improve deployed latency further

## License

See [LICENSE](LICENSE).
