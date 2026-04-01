# SmartPantry

SmartPantry is a full-stack, AI-assisted kitchen inventory app built around a human-in-the-loop workflow. Users can upload pantry or fridge photos, review detection proposals before anything is saved, maintain a structured inventory, and discover recipes ranked against current pantry state.

## Highlights

- Account system with registration, login, display names, timezone support, account editing, and inactivity-aware session refresh
- Inventory CRUD with inline editing, category grouping, quick add, and AI-assisted Smart Add
- Cloud-backed image storage with Cloudflare R2
- Fine-tuned YOLOv8n-based detection with explicit user review before inventory changes are persisted
- Grouped review, per-box review, and manual point-add for missed detections
- Recent upload history with thumbnail previews and retention cleanup
- Inventory-aware recipe recommendations with feedback, favorites, and reusable hashtags
- OpenAI-backed pantry assistant that explains which recipes best fit current inventory, mood, priority ingredients, and older perishables
- RAG groundwork for Ask SmartPantry recipe Q&A with recipe embeddings stored in Postgres
- Pantry follow-through flow that lets users review inventory changes after cooking
- Measured deployment and model-improvement benchmarks for both latency and detector quality

## Major Milestones

### 1. Human-in-the-loop pantry vision workflow

- Shipped Smart Add as a review-first computer vision workflow rather than auto-committing detections
- Kept confirmed inventory as the source of truth for all downstream features
- Added grouped review, per-box review, and manual point-add so users can correct model output before any state changes are saved

### 2. Pantry-domain detector improvement and deployment

- Benchmarked a generic pretrained YOLOv8n baseline against the pantry taxonomy
- Built training and evaluation scripts for reproducible fine-tuning and held-out test benchmarking
- Fine-tuned YOLOv8n on the pantry dataset and redeployed the improved checkpoint to the production backend
- Measured both detector-quality gains and deployed latency after rollout

### 3. LLM-assisted recipe guidance

- Added an OpenAI-backed pantry assistant on top of deterministic recipe ranking instead of replacing the existing recommendation engine
- Let users ask for pantry-aware recipe shortlists using mood, time limit, priority ingredients, and older perishables as signals
- Kept the assistant advisory-only with structured JSON responses and backend-controlled candidate validation

### 4. Grounded recipe Q&A with RAG

- Added recipe embeddings stored in Postgres and built an Ask SmartPantry flow for natural-language recipe questions
- Implemented pantry-aware retrieval and reranking before generation so answers stay tied to actual recipe records
- Constrained generated recipe references to retrieved candidate IDs instead of trusting freeform model output

## Current Architecture

```text
Next.js frontend on Vercel
  -> Vercel server-side proxy route
      -> FastAPI backend on AWS EC2 (Docker + Nginx)
          -> Neon PostgreSQL
          -> Cloudflare R2 for uploaded image blobs
          -> In-process fine-tuned YOLOv8n detection on CPU
```

Key design choices:

- Confirmed inventory is the source of truth. Detection proposals are always reviewable and never auto-committed.
- The frontend stays on Vercel, but browser requests go through a same-origin proxy route instead of calling the EC2 backend directly.
- Structured application state lives in the database, while uploaded image bytes live in object storage.
- The deployed detector uses a pantry-finetuned YOLOv8n checkpoint instead of the generic pretrained baseline.
- Recipe ranking is deterministic and explainable.
- The pantry assistant is additive: the backend still ranks recipe candidates deterministically first, then uses an LLM to explain and prioritize the best few options.
- Ask SmartPantry uses a first-pass RAG design: embed recipe documents, retrieve semantically relevant candidates, rerank with pantry signals, and only then ask the LLM to synthesize an answer.
- Recipe follow-through is conservative and user-reviewed instead of silently inferred.

Selected measured results:

- Smart Add latency on the deployed public path improved from `695.5 ms` p50 / `838.4 ms` p95 to `689.9 ms` p50 / `752.7 ms` p95 after deploying the fine-tuned model
- Direct backend Smart Add latency improved from `644.2 ms` p50 / `734.1 ms` p95 to `584.7 ms` p50 / `665.6 ms` p95 after deploying the fine-tuned model
- Held-out pantry test-set quality improved from `0.020` to `0.472` mAP@50 and from `0.018` to `0.361` mAP@50-95 after YOLOv8n fine-tuning

## Tech Stack

- Frontend: Next.js 14, React 18
- Backend: FastAPI, SQLAlchemy, Pydantic
- LLM integration: OpenAI Responses API (`gpt-5-mini`) with structured JSON output
- Detection: Ultralytics YOLOv8n, pantry-domain fine-tuning, custom evaluation scripts
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
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_ASSISTANT_ENABLED`
- `OPENAI_ASSISTANT_TIMEOUT_SECONDS`
- `OPENAI_ASSISTANT_MAX_RECIPES`
- `OPENAI_ASSISTANT_MAX_PANTRY_ITEMS`
- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_RAG_ENABLED`
- `OPENAI_RAG_TIMEOUT_SECONDS`
- `OPENAI_RAG_MAX_RETRIEVALS`
- `OPENAI_RAG_MAX_CONTEXT_RECIPES`

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

RAG evaluation guidance:

- verify indexing correctness first: one embedding row per recipe and clean retrieval document text
- inspect top-k retrieval quality separately from final answer quality
- check groundedness: generated recipe references should stay inside the retrieved candidate set
- test fallback behavior for empty retrievals, upstream API failures, and restrictive user questions
- treat latency, error rate, and per-request cost as production metrics, not just model-quality concerns

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
- The pantry assistant and Ask SmartPantry are grounded and validated, but they are still advisory rather than sources of truth
- The deployed backend currently uses an EC2 public IP plus Vercel proxying rather than a custom backend domain
- The fine-tuned checkpoint is mounted from the EC2 host into the backend container rather than stored in git or a model registry

## License

See [LICENSE](LICENSE).
