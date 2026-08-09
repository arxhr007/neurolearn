# Run Guide

For the normal setup — Docker, or running the API and web app locally — see
[RUNNING.md](RUNNING.md). This file covers the extras: the CLI tutor and the
data pipeline.

All Python commands below are run from the `backend/` directory.

## 1. One-time setup

```bash
cd backend
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only build
pip install -r requirements.txt
```

Create your environment file and set the required keys:

```bash
cp .env.example .env
# Set GROQ_API_KEY, gemini_api_key, and JWT_SECRET_KEY
```

`.env` is read from the repository root or from `backend/.env`; if both exist,
`backend/.env` wins.

The database directory is created automatically on first run. Retrieval works
out of the box from the chunk corpus in `backend/output/rag_chunks/`, so
building a vector index is optional:

```bash
python pipeline/build_vector_index.py
```

## 2. Run the CLI tutor

Interactive tutor session:

```bash
python main.py --student-id s100
```

Single-question mode:

```bash
python main.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

Optional retrieval tuning:

```bash
python main.py --student-id s100 \
  --retrieval-candidate-k 20 \
  --retrieval-min-similarity 0.35
```

## 3. Run the JSON API only

```bash
python -m uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload
```

```text
http://localhost:8000/api/health
http://localhost:8000/api/docs
http://localhost:8000/api/redoc
```

This is what the React app and the Docker image use.

If `uvicorn` is not on your PATH, use the `python -m uvicorn ...` form.

## 4. Verify

```bash
curl -sS http://localhost:8000/api/health
python test_api.py
pytest tests/
```

## 5. Data and pipeline commands

Inspect or create a student profile:

```bash
python manage_student_db.py
```

Build or refresh the vector index:

```bash
python pipeline/build_vector_index.py
```

Regenerate chunk files from the source PDFs. This needs Tesseract (with the
Malayalam language pack) and Poppler installed, and reads `backend/input/pdfs/`:

```bash
python pipeline/pdf_content_pipeline.py
python pipeline/build_vector_index.py
```

## 6. Shortest path to a running stack

```bash
cp .env.example .env      # add your API keys
docker compose up --build
```
