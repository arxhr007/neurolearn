# Deployment

NeuroLearn ships as two containers: the FastAPI backend and an nginx-served
React app. See [RUNNING.md](../RUNNING.md) for the day-to-day commands.

## Layout

```
backend/     FastAPI API, LangGraph tutor, RAG pipeline, curriculum data
frontend/    React + Vite SPA, built and served by nginx
compose.yaml         production stack
compose.dev.yaml     development overlay (bind mounts, hot reload)
```

## Deploy

```bash
cp .env.example .env      # set GROQ_API_KEY and gemini_api_key
docker compose up --build
```

The web app listens on port 3000 and the API on 8000. nginx proxies `/api` to
the backend, so the browser only ever talks to one origin and CORS is not
involved.

## What the image contains

- CPU-only PyTorch. The default CUDA build adds roughly 2.5 GB the project
  never uses.
- The `paraphrase-multilingual-MiniLM-L12-v2` embedding model, baked in at
  build time so startup needs no network access.
- The chunked corpus in `backend/output/rag_chunks/`, which the retriever falls
  back to when no Chroma index is present. Retrieval therefore works on a fresh
  deploy with no pipeline run.
- Source PDFs are excluded via `backend/.dockerignore`; they are only inputs to
  the offline OCR pipeline.

## Persistence

`backend/data/` (SQLite), `backend/vectorstore/` (Chroma), and
`backend/checkpoints/` (LangGraph) are bind-mounted, so they survive
`docker compose down`. Back up `backend/data/neurolearn.db` to back up all user
data.

## Before exposing this publicly

The current build is suitable for local and internal use. Outstanding items:

- `ALLOW_DEV_USERS` defaults to true and enables hardcoded accounts
  (`admin@neurolearn.local` / `admin123` and equivalents). Set it to false.
- `JWT_SECRET_KEY` must be set to a real secret; the default is a placeholder.
- The bootstrap admin is created as `admin` / `admin`. Change the password.
- `POST /api/story/tts` has no authentication and calls a paid API.
- Refresh tokens are not distinguishable from access tokens and are never
  revoked, so logout does not invalidate a stolen token.
- Serve over TLS and set `SESSION_COOKIE` flags accordingly.
- SQLite is fine for a single instance; move to a managed database before
  running more than one backend replica, since the SQLite file is not shared.
