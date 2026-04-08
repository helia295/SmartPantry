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
- recipe embeddings, retrieval, and grounded recipe question-answering infrastructure
- storage abstraction for local filesystem and Cloudflare R2
- startup and recurring cleanup of expired uploaded images
- pantry-specific YOLO checkpoint loading and detection warmup

## Current Milestones

### Pantry assistant milestone

- deterministic recipe ranking remains the first-stage candidate generator
- OpenAI is used as a grounded explanation and prioritization layer rather than a replacement for core application logic
- user controls include mood/request text, optional time constraint, explicit ingredient priorities, and older-perishable prioritization

### Ask SmartPantry RAG milestone

- recipe embeddings are stored in the database for retrieval
- query-time retrieval is pantry-aware and reranked before generation
- generated answers are filtered so only retrieved recipe IDs survive
- the v1 retrieval design uses one embedding document per recipe to keep indexing, debugging, and rollout simpler
- preview mode can expose the UX shell safely on a public deployment without triggering paid OpenAI traffic

### Learned ranker milestone

- deterministic candidate generation remains in place for filtering, pantry grounding, and fallback behavior
- an optional XGBoost reranker can reorder candidate recipes on top of those deterministic features
- offline training now uses a context-level holdout split and compares the learned model against the deterministic baseline
- runtime learned ranking is config-gated so the deployed app can stay deterministic until the artifact and optional dependency set are intentionally enabled
- on held-out validation contexts, the learned reranker improved `Hit@1` from `0.9563` to `0.9885` and `NDCG@5` from `0.9830` to `0.9957`

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
alembic upgrade head
```

That default install is enough for the deterministic recommender path and the rest of the backend.

If you want to train or serve the learned recipe ranker locally, install the optional ranker extra too:

```bash
pip install -e ".[dev,ml,ranker]"
```

Run locally:

```bash
uvicorn app.main:app --reload --port 8000
```

Important note:

- backend startup now assumes the schema is already provisioned
- if you are on a fresh or outdated database, run `alembic upgrade head` before starting Uvicorn or the Docker container

OpenAPI docs:

- `http://localhost:8000/docs`

## Docker

Build locally:

```bash
cd backend
docker build -t smartpantry-backend .
```

Deployment note:

- the Dockerfile is tuned for a CPU deployment target and installs PyTorch from the CPU wheel index
- this avoids pulling unnecessary CUDA/NVIDIA packages into the EC2 image build
- the runtime image now also installs the optional `ranker` extra so the deployed backend can load the XGBoost reranker artifact when `RECIPE_RANKER_MODE=learned`

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
- `OPENAI_ASSISTANT_PREVIEW_ONLY`
- `OPENAI_ASSISTANT_TIMEOUT_SECONDS`
- `OPENAI_ASSISTANT_MAX_RECIPES`
- `OPENAI_ASSISTANT_MAX_PANTRY_ITEMS`
- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_RAG_ENABLED`
- `OPENAI_RAG_PREVIEW_ONLY`
- `OPENAI_RAG_TIMEOUT_SECONDS`
- `OPENAI_RAG_MAX_RETRIEVALS`
- `OPENAI_RAG_MAX_CONTEXT_RECIPES`
- `OPENAI_FEATURES_REPO_URL`

Learned recipe ranker:

- `RECIPE_RANKER_MODE`
- `RECIPE_RANKER_MODEL_PATH`

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
- allows a backend-controlled preview mode for public deployments that should show the workflow without spending live API credits

## Learned Recipe Ranker Design

The recommendation stack now has two ranking modes:

1. deterministic mode
2. learned reranker mode

The shared flow is:

1. load confirmed pantry inventory and user feedback
2. generate candidate recipes with the existing deterministic filtering rules
3. compute structured candidate features such as pantry overlap, missing ingredients, requested main-ingredient matches, time fit, and recipe metadata
4. either:
   - score candidates with the deterministic heuristic ranker, or
   - score them with the XGBoost reranker if `RECIPE_RANKER_MODE=learned`
5. fall back to deterministic scoring automatically if the learned model artifact or optional dependency is unavailable

Why this design:

- keeps the recommendation API stable for the frontend, pantry assistant, and RAG flows
- avoids scoring the full recipe corpus online on a small CPU-only deployment target
- preserves a safe deterministic path if the learned model fails to load
- gives the model a real chance to improve ordering without weakening hard product constraints such as dislikes and time filtering

## Ask SmartPantry RAG Design

The Ask SmartPantry flow is the second-stage LLM feature in the app.

The backend flow is:

1. embed the user question with the OpenAI embeddings model
2. retrieve semantically relevant recipe documents from `recipe_embeddings`
3. rerank retrieved recipes with pantry overlap, missing-ingredient penalties, and optional time constraints
4. pass only the top grounded candidates plus compact pantry context to the generation model
5. validate the generated output and drop any recipe references that were not in the retrieved set

Why this design:

- retrieval quality can be debugged independently from generation quality
- the model answers over recipe evidence rather than generic cooking knowledge
- pantry-aware reranking keeps the feature aligned with the existing SmartPantry product loop
- output filtering reduces hallucination risk and makes the response safer to render directly in the UI
- preview mode can keep the public UX coherent even when the live generation path is intentionally disabled

## Recipe API Surface

Current routes include:

- `POST /recipes/assistant/use-up`
- `POST /recipes/assistant/ask`
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
- recipe Q&A is grounded on embedded recipe documents plus pantry-aware reranking before generation
- older perishable pantry items can be surfaced as an explicit prioritization signal to the assistant
- users can also explicitly prioritize specific pantry ingredients from the UI, and those ingredients are used both for candidate ranking bias and assistant guidance
- recommendations are ranked against confirmed inventory
- dislikes are excluded from future recommendation pages
- likes are saved to the favorite recipe book
- hashtags organize favorites without introducing heavier collection management
- pantry follow-through remains conservative and explicitly reviewed

## Retrieval and Embedding Workflow

The Ask SmartPantry groundwork uses a simple one-document-per-recipe retrieval design for v1.

Backend pieces:

- `recipe_embeddings` table stores one embedding row per recipe
- `index_recipe_embeddings.py` builds recipe documents and writes embeddings
- retrieval first searches embedded recipe documents, then reranks with pantry overlap
- the LLM only sees the top grounded recipe candidates rather than the full recipe corpus

This keeps the first RAG version easier to reason about, cheaper to run, and consistent with the grounded design used for the pantry assistant.

How to evaluate the RAG path in practice:

- indexing: verify document counts, document text quality, and successful upserts into `recipe_embeddings`
- retrieval: inspect top-k candidates for a small golden query set before judging the final LLM answer
- groundedness: verify the answer never references recipe IDs outside the retrieved set
- usefulness: check whether answers are materially better than deterministic recommendation alone for natural-language questions
- reliability: measure latency, timeout rate, and failure behavior, especially for empty or weak retrievals

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

Current public-demo posture:

- the public deployment can run both AI recipe surfaces in preview mode
- preview mode keeps the UI visible and explains how to self-host the real feature
- the manual `Find Recipe` path remains available even when live AI is disabled

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

- migration-first deployment is now the intended path, but rollout discipline matters because startup no longer creates tables for you
- current rate limiting is in-memory rather than distributed
- no custom backend domain yet
- detection still runs inline rather than via a dedicated worker or queue
- Ask SmartPantry still needs a production rollout checklist: migration on Neon, embedding indexing against the deployed recipe dataset, backend env updates, and post-deploy smoke testing
