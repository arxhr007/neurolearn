# Running NeuroLearn

## Repository layout

```
neurolearn/
├── backend/          FastAPI API, LangGraph tutor, RAG pipeline, curriculum data
├── frontend/         React + Vite single-page app
├── website/          legacy static API console (not part of the running stack)
├── docs/
├── compose.yaml      production stack
└── compose.dev.yaml  development overlay (hot reload)
```

---

## Quick start with Docker

Two commands, start to finish:

```bash
cp .env.example .env      # then fill in GROQ_API_KEY and gemini_api_key
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/api/docs |

Sign in with `admin` / `admin`.

The first build takes a while: it installs CPU-only PyTorch and bakes the
multilingual embedding model into the image so that startup needs no network
access. Later builds are cached.

The backend answers questions using the pre-chunked corpus committed at
`backend/output/rag_chunks/`, so retrieval works immediately — you do not need
to run the OCR pipeline or build a vector index first.

### Development with hot reload

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Source directories are bind-mounted, `uvicorn` runs with `--reload`, and the
web app is served by Vite on http://localhost:5173.

### Data persistence

SQLite databases and the Chroma index are bind-mounted to `backend/data/`,
`backend/vectorstore/`, and `backend/checkpoints/`, so they survive
`docker compose down`. To wipe them, delete those directories.

---

## Running without Docker

Requirements: Python 3.10+, Node.js 18+, npm 9+.

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload
```

The SQLite database is created automatically at `backend/data/neurolearn.db`
on first run, along with a default `admin` / `admin` account.

`.env` is read from the repository root or from `backend/.env`; if both exist,
`backend/.env` wins.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173 and proxies `/api` to http://localhost:8000, so
there is no CORS configuration to do. Point it elsewhere with
`VITE_DEV_API_TARGET` — see `frontend/.env.example`.

Production build:

```bash
npm run build      # output in frontend/dist/
```

The app issues same-origin requests to `/api/...`, so whatever serves `dist/`
must also proxy `/api` to the backend. `frontend/nginx.conf` is a working
example. Only set `VITE_API_BASE_URL` if the API is on a genuinely different
origin, and add that origin to `CORS_ORIGINS_RAW` if you do.

---

## API keys

**Groq** — tutor answers and chapter generation. Sign up at
https://console.groq.com, create a key, set `GROQ_API_KEY`.

**Gemini** — story generation, TTS audio, and memory transcription. Get a key
at https://aistudio.google.com/apikey (starts with `AIza...`), set
`gemini_api_key`. The free tier allows roughly 15 TTS requests per minute.

Without `GROQ_API_KEY` the app still starts and you can sign in, but tutor
endpoints return 503.

---

## Common issues

**502 on TTS** — Gemini rate limit. Wait ~60 seconds and retry.

**404 after refreshing a page like `/student/chat`** — whatever is serving the
SPA is missing the history-API fallback. It needs to return `index.html` for
unknown paths; see the `try_files` line in `frontend/nginx.conf`.

**CORS errors** — the Docker and Vite setups both serve the API on the app's
own origin, so this should not happen. If you are hosting the frontend
separately, add its origin to `CORS_ORIGINS_RAW` and restart the backend.

**`unable to open database file`** — the backend is running from a directory
without a writable `data/`. Run it from `backend/`, or create `backend/data/`.
