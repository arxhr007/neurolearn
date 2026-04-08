# Deployment

NeuroLearn is currently CLI-first, so deployment mainly means packaging the tutor runtime and its local dependencies cleanly.

## Current state

- Main runtime: `main.py`
- Student admin: `manage_student_db.py`
- Optional content pipeline: `pipeline/pdf_content_pipeline.py` and `pipeline/build_vector_index.py`
- Local persistence: SQLite plus Chroma vector store

## Required environment

- Python 3.9+
- `GROQ_API_KEY`
- Tesseract OCR and Malayalam data if you use the PDF pipeline
- Poppler if you use PDF processing

## Local deployment checklist

1. Install dependencies.
2. Set `.env`.
3. Create at least one student profile.
4. Build the vector index if you want custom content.
5. Run `main.py` with a valid `--student-id`.

## What would change for online hosting

- Replace SQLite with a managed database.
- Replace local Chroma persistence with a hosted vector store.
- Wrap the CLI in a web or API layer.
- Add authentication and request limits.
- Move file uploads and OCR jobs into a background worker.

## Practical advice

If you want to publish the project before building a web app, keep the current CLI docs accurate and mark the online story as future work instead of promising a hosted deployment that does not exist yet.

