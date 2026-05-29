# Run Guide

This file collects the supported ways to run NeuroLearn from a fresh checkout.

## 1. One-time setup
Install dependencies:

```bash
source /home/antony/neurolearn/myenv/bin/activate
pip install langgraph-checkpoint-sqlite
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
python3 -m pip install -r requirements.txt
```

Create your environment file and set the required keys:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY, JWT_SECRET_KEY, and any other values you want to override
```

Create the local database directory used by the web app:

```bash
mkdir -p data
python3 pipeline/build_vector_index.py
```

If you want to use the repository's bundled data, no OCR rebuild is needed. If you want to regenerate the vector store, run the optional pipeline steps below.

## 2. Run the CLI tutor

Interactive tutor session:

```bash
python3 main.py --student-id s100
```

Single-question mode:

```bash
python3 main.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

Optional retrieval tuning:

```bash
python3 main.py --student-id s100 \
  --retrieval-candidate-k 20 \
  --retrieval-min-similarity 0.35
```

## 3. Run the FastAPI backend

Start the API server:

```bash
python3 -m uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload
```

Useful API URLs:

```text
http://localhost:8000/api/health
http://localhost:8000/api/docs
http://localhost:8000/api/redoc
```

## 4. Run the full web app

Start the web app with the Jinja pages and API together:

has reload- for dev
```bash
python3 -m uvicorn web_main:app --host 0.0.0.0 --port 8000 --reload
```

no reload-for production
```bash
python3 -m uvicorn web_main:app --host 0.0.0.0 --port 8000
```
If `uvicorn` is not on your PATH, always use the `python3 -m uvicorn ...` form.

## 5. Run with Docker

Build and start the container stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

## 6. Verify the app

Check API health:

```bash
curl -sS http://localhost:8000/api/health
```

Run the smoke test script:

```bash
python3 test_api.py
```

## 7. Optional data and pipeline commands

Inspect or create a student profile:

```bash
python3 manage_student_db.py
```

Build or refresh the vector index:

```bash
python3 pipeline/build_vector_index.py
```

Regenerate chunk files from PDFs:

```bash
python3 pipeline/pdf_content_pipeline.py
python3 pipeline/build_vector_index.py
```

## 8. Common launch order

If you want the shortest path to a working web app, run these in order:

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
mkdir -p data
python3 -m uvicorn web_main:app --host 0.0.0.0 --port 8000 --reload
```


## 9. Story Mode (opt-in)

Story Mode converts a generated answer into a short, learner-friendly Malayalam story. It is opt-in and does not change stored conversation history or the original answer.

Interactive usage:

- Start the interactive CLI as usual:

```bash
python3 main.py --student-id <STUDENT_ID>
```

- After asking a question and receiving an answer, type `story` at the prompt to get a storyified version of the last answer.

Single-query (non-interactive) usage:

```bash
python3 main.py --text "Why wash hands?" --student-id <STUDENT_ID> --story
```

API endpoint:

- A read-only endpoint was added to request a story for a previously saved conversation turn (requires auth):

```
GET /api/conversations/{student_id}/{conversation_id}/{turn_id}/story
```

Replace the placeholders and call with a valid bearer token. Example (curl):

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://localhost:8000/api/conversations/s100/CONVO_ID/TURN_ID/story"
```

Testing:

- Run the lightweight story-mode unit test:

```bash
pytest -q tests/test_story_mode.py
```

---
