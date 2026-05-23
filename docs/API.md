# NeuroLearn API Reference

This document is a concise API reference for the FastAPI service in `api_main.py`.

## Base URLs

- Local base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- Redoc: `http://localhost:8000/api/redoc`

## Auth Model

The API uses JWT bearer tokens. Get an access token from `/api/auth/login` and send it in the `Authorization` header.

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Tokens are short-lived (see `expires_in`); refresh tokens are longer-lived.

## Roles and Access

- `student`: tutor endpoints + read-only student profile, mastery, goals, conversations.
- `teacher`: student permissions + update student profile + create goals + read admin stats/config.
- `admin`: all teacher permissions + update retriever config.

## Quickstart

```bash
uvicorn api_main:app --host 0.0.0.0 --port 8000
```

Dev users (local):
- `student@neurolearn.local` / `student123`
- `teacher@neurolearn.local` / `teacher123`
- `admin@neurolearn.local` / `admin123`

## Common Errors

- `401 Invalid authentication credentials`: missing or expired token.
- `403 Insufficient permissions`: role not allowed for endpoint.
- `404 Student not found: <id>`: student profile missing.
- `503 Tutor service unavailable`: usually missing `GROQ_API_KEY` or LLM init error.

## Endpoints

### Meta

- `GET /`
  - Returns: `{ name, version, docs }`

- `GET /api/health`
  - Returns overall health and service map.

### Auth

- `POST /api/auth/login`
  - Body:
    ```json
    {
      "email": "student@neurolearn.local",
      "password": "student123",
      "role": "student"
    }
    ```
  - Returns: access + refresh tokens and user metadata.

- `POST /api/auth/refresh`
  - Body:
    ```json
    { "refresh_token": "<jwt>" }
    ```

- `POST /api/auth/logout`
  - Requires bearer token. Stateless; returns success message.

### Tutor

- `POST /api/tutor/question`
  - Role: `student`, `teacher`, `admin`
  - Body:
    ```json
    {
      "student_id": "s100",
      "conversation_id": "<uuid>",
      "question": "Why is handwashing important?",
      "context": {
        "top_k": 5
      }
    }
    ```
  - Notes:
    - `conversation_id` must be provided by the client.
    - `context.top_k` is optional and overrides the default retrieval depth.
  - Returns:
    - `answer`: tutor response
    - `check_question`: follow-up check question (nullable)
    - `check_answer_hint`: hidden expected-answer hint (nullable)
    - `sources`: list of retrieval sources (may be empty)
    - `status`: `answered` or `waiting_for_answer`

- `POST /api/tutor/answer`
  - Role: `student`, `teacher`, `admin`
  - Body:
    ```json
    {
      "student_id": "s100",
      "conversation_id": "<uuid>",
      "turn_id": "<turn_id_from_question>",
      "student_answer": "Because it prevents germs.",
      "check_answer_hint": "optional"
    }
    ```
  - Returns evaluation with `is_correct`, `feedback`, `confidence`, and optional remediation.

### Conversations

- `GET /api/conversations/{student_id}?limit=10`
  - Returns the latest in-memory conversation snapshot for the student.

- `GET /api/conversations/{student_id}/{conversation_id}`
  - Returns a conversation by id.

- `DELETE /api/conversations/{conversation_id}`
  - Deletes a conversation from in-memory history.

### Students

- `GET /api/students/{student_id}`
  - Returns the student profile.

- `PUT /api/students/{student_id}`
  - Role: `teacher`, `admin`
  - Body:
    ```json
    {
      "name": "Test User",
      "learning_style": "analogy-heavy",
      "reading_age": 12,
      "interests": ["chess", "football"],
      "neuro_profile": ["adhd", "dyslexia"]
    }
    ```

### Mastery

- `GET /api/students/{student_id}/mastery?limit=20&offset=0&concept_key=<optional>`
  - Returns mastery event history.

- `GET /api/students/{student_id}/mastery/stats?recent_days=7`
  - Returns aggregate mastery statistics.

### Learning Goals

- `GET /api/students/{student_id}/goals`
  - Returns active and archived goals.

- `POST /api/students/{student_id}/goals`
  - Role: `teacher`, `admin`
  - Body:
    ```json
    { "goal_text": "Learn handwashing and hygiene basics" }
    ```

### Admin

- `GET /api/admin/retriever/config`
  - Role: `teacher`, `admin`
  - Returns retriever configuration.

- `PATCH /api/admin/retriever/config`
  - Role: `admin`
  - Body:
    ```json
    {
      "candidate_k": 25,
      "min_similarity": 0.32,
      "dedup_max_per_source_page": 1,
      "rerank_enabled": true,
      "hybrid_enabled": false
    }
    ```
  - Notes:
    - `top_k` is computed server-side and not updated by this endpoint.

- `GET /api/admin/system/stats`
  - Role: `teacher`, `admin`
  - Returns service stats and health.

## Example Flow (curl)

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@neurolearn.local","password":"student123","role":"student"}'

# Ask a question
curl -X POST http://localhost:8000/api/tutor/question \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"student_id":"s100","conversation_id":"<uuid>","question":"Why is handwashing important?","context":{}}'
```

## Notes

- Conversation history is in-memory and resets when the server restarts.
- The tutor requires `GROQ_API_KEY` to initialize the LLM.
- RAG sources are included in `sources` when retrieval is successful.
