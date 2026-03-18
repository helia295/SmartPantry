# SmartPantry

AI-powered kitchen inventory: upload pantry photos, review AI proposals, and get recipe recommendations—with you in the loop.

## Repo layout

- **backend/** — FastAPI app (auth, images, detection, inventory, recipes)
- **frontend/** — Next.js (App Router)
- **.github/workflows/** — CI

## Tooling

- Node.js: `20.20.1` via the repo-level `[.nvmrc](/Users/heliadinh/Desktop/CS personal projects/SmartPantry/.nvmrc)`
- Python: `>=3.10` for the backend

If you use `nvm`, run this from the repo root before working on the frontend:

```bash
nvm use
node -v
npm -v
```

Next.js 14 requires Node `>=18.17.0`. Using mixed Node versions across shells can break `npm install`, `next dev`, and `next build`.

## Local dev

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev,ml]"
uvicorn app.main:app --reload --port 8000
```

API: [http://localhost:8000](http://localhost:8000) — Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

If you want the backend to prefer YOLO proposals, keep `DETECTION_PROVIDER=yolo`. The app will still fall back to the mock detector if YOLO or its dependencies fail at runtime.

### Frontend

```bash
cd ..
nvm use
cd frontend
npm ci
npm run dev
```

App: [http://localhost:3000](http://localhost:3000) — Proxies API to backend via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

If frontend dependencies ever look corrupted, the safe recovery path is:

```bash
cd frontend
rm -rf node_modules
npm ci
```

### Env

Copy `.env.example` and set `NEXT_PUBLIC_API_URL` for the frontend; backend can run with defaults.

## CI

On push/PR to `main`: backend tests (pytest), frontend lint + build.

## Milestones

1. **Scaffold & hello world** : health check, landing page, CI.
2. **Auth + inventory foundation**: user auth, timezone, inventory CRUD.
3. **Image upload + detection sessions**: authenticated upload, storage abstraction, proposal persistence.
4. **Detection review UX**: grouped/per-box review, manual point-add, YOLO path with mock fallback.
5. **Human-in-the-loop confirmation**: confirm/add/update/reject flow with inventory change logs.
6. **Recipe recommendations**: inventory-aware ranking, recipe detail page, like/dislike and saved recipe book.
7. **Deployment hardening**: production env docs, CORS, secret handling, storage guidance.
8. **Performance, limits, polish**: rate limiting, cleanup jobs, evaluation, README refresh.

## License

See [LICENSE](LICENSE).