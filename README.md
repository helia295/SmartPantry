# SmartPantry

AI-powered kitchen inventory: upload pantry photos, review AI proposals, and get recipe recommendations—with you in the loop.

## Repo layout

- **backend/** — FastAPI app (auth, images, detection, inventory, recipes)
- **frontend/** — Next.js (App Router)
- **.github/workflows/** — CI

## Local dev

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000 — Docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000 — Proxies API to backend via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

### Env

Copy `.env.example` and set `NEXT_PUBLIC_API_URL` for the frontend; backend can run with defaults for Milestone 1.

## CI

On push/PR to `main`: backend tests (pytest), frontend lint + build.

## Milestones

1. **Scaffold & hello world** — Done: health check, landing page, CI.
2. Auth + DB (User, InventoryItem), inventory CRUD.
3. Image upload + DetectionSession.
4. Detection model (YOLO) + proposals.
5. Human-in-the-loop review UI + confirm.
6. Recipe recommendations.
7. Tests, rate limits, polish.

## License

See [LICENSE](LICENSE).
