# Running NeuroLearn

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

---

## 1. Clone and set up environment

```bash
git clone <repo-url>
cd neurolearn
```

Copy the env template and fill in your API keys:

```bash
cp .env.example .env   # or create .env manually
```

**.env contents:**

```env
# Required — story/chapter generation
GROQ_API_KEY=your_groq_api_key_here

# Required — TTS audio (get from https://aistudio.google.com/apikey)
gemini_api_key=your_gemini_api_key_here

# Story generation provider (gemini or groq)
story_provider=gemini
gemini_model=gemini-2.0-flash

# JWT secret — change this in production
JWT_SECRET_KEY=change-this-in-production

# CORS — add any frontend origins you use
CORS_ORIGINS_RAW=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

---

## 2. Backend (FastAPI)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run

```bash
python -m uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload
```

API runs at: `http://localhost:8000`

Interactive API docs: `http://localhost:8000/docs`

### First-time database setup

The SQLite database is created automatically at `data/neurolearn.db` on first run.

To create an admin account:

```bash
python manage_student_db.py
```

---

## 3. Frontend (React + Vite)

### Install dependencies

```bash
cd frontend
npm install
```

### Run (development)

```bash
npm run dev
```

Frontend runs at: `http://localhost:5173`

### Build for production

```bash
npm run build
```

Output goes to `frontend/dist/`. Serve it with any static file server or configure the FastAPI backend to serve it.

---

## 4. Default accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Teacher | (create via admin panel) | — |
| Student | (create via teacher panel) | — |

---

## 5. API Keys

### Groq (story/chapter generation)
- Sign up at https://console.groq.com
- Create an API key
- Add as `GROQ_API_KEY` in `.env`

### Gemini (TTS audio)
- Go to https://aistudio.google.com/apikey
- Create an API key (starts with `AIza...`)
- Add as `gemini_api_key` in `.env`
- Free tier has rate limits (~15 requests/min for TTS). If you hit 429 errors, wait 60 seconds and retry.

---

## 6. Common issues

**Backend 502 on TTS**
Gemini API rate limit hit. Wait ~60 seconds and try generating audio again. Check your quota at https://aistudio.google.com.

**CORS errors in browser**
Add your frontend URL to `CORS_ORIGINS_RAW` in `.env`, then restart the backend.

**`data/neurolearn.db` missing**
Start the backend once — it auto-creates the database file.

**Frontend shows blank page**
Make sure the backend is running on port 8000 before opening the frontend.
