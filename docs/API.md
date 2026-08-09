# NeuroLearn API Reference

This document covers the JSON API in `backend/api_main.py`. It is the only
server interface — the React app in `frontend/` is its sole client.

## Base URLs

- API base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- Redoc: `http://localhost:8000/api/redoc`

Under Docker the web app is served on `http://localhost:3000` and proxies
`/api` to this backend, so browser requests are same-origin.

## Authentication

### Bearer tokens (JSON API)

Use `/api/auth/login` to obtain an access token. Send it in the `Authorization` header for all protected endpoints.

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

Tokens are short-lived (see `expires_in`); refresh tokens are longer-lived.

## Roles and Access

- `student`: tutor endpoints + read-only student profile, mastery, goals, conversations.
- `teacher`: student permissions + manage teacher students and goals + view teacher stats.
- `admin`: all teacher permissions + manage teachers + update retriever config.

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
- `404 Student not found`: student profile missing.
- `429 Too many login attempts`: web login rate limit triggered.
- `503 Tutor service unavailable`: usually missing `GROQ_API_KEY` or LLM init error.

## JSON API Endpoints

### Meta

- `GET /`
  - Returns: `{ name, version, docs }`

- `GET /api/health`
  - Returns overall health and service map.

### Authentication

- `POST /api/auth/login`
  - Body:
    ```json
    {
      "email": "student@neurolearn.local",
      "password": "student123",
      "role": "student"
    }
    ```
  - Returns: access and refresh tokens plus user metadata.

- `POST /api/auth/refresh`
  - Body:
    ```json
    { "refresh_token": "<jwt>" }
    ```
  - Returns: same shape as login response.

- `POST /api/auth/logout`
  - Requires bearer token. Stateless; returns `{ "message": "Logged out successfully" }`.

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
  - Returns: `conversation_id`, `turn_id`, `answer`, optional `check_question`, optional `check_answer_hint`, `sources`, `status`, `generated_at`.

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
  - Returns evaluation with `is_correct`, `feedback`, `confidence`, and optional `remediation`.

### Conversations (Tutor service history)

- `GET /api/conversations/{student_id}?limit=10`
  - Role: `student`, `teacher`, `admin`
  - Returns the tutor service conversation history (may be in-memory).

- `GET /api/conversations/{student_id}/{conversation_id}`
  - Role: `student`, `teacher`, `admin`
  - Returns a single tutor conversation by id.

- `DELETE /api/conversations/{conversation_id}`
  - Role: `student`, `teacher`, `admin`
  - Deletes a conversation from tutor history.

### Students

- `GET /api/students/{student_id}`
  - Role: `student`, `teacher`, `admin`
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
  - Role: `student`, `teacher`, `admin`
  - Returns mastery event history.

- `GET /api/students/{student_id}/mastery/stats?recent_days=7`
  - Role: `student`, `teacher`, `admin`
  - Returns aggregate mastery statistics.

### Learning Goals

- `GET /api/students/{student_id}/goals`
  - Role: `student`, `teacher`, `admin`
  - Returns active and archived goals.

- `POST /api/students/{student_id}/goals`
  - Role: `teacher`, `admin`
  - Body:
    ```json
    { "goal_text": "Learn handwashing and hygiene basics" }
    ```

### Admin - Teacher Management

- `GET /api/admin/teachers`
  - Role: `admin`
  - Returns `{ total, teachers[] }`.

- `POST /api/admin/teachers`
  - Role: `admin`
  - Body:
    ```json
    { "username": "teacher1", "password": "secret", "full_name": "Teacher One" }
    ```
  - Returns the created teacher.

- `GET /api/admin/teachers/{teacher_id}`
  - Role: `admin`
  - Returns one teacher by id.

- `PUT /api/admin/teachers/{teacher_id}`
  - Role: `admin`
  - Body:
    ```json
    { "full_name": "Teacher One", "password": "newpass", "is_active": true }
    ```

### Teacher - Student Management

- `GET /api/teacher/students`
  - Role: `teacher`
  - Returns `{ total, students[] }`.

- `POST /api/teacher/students`
  - Role: `teacher`
  - Body:
    ```json
    {
      "student_id": "s100",
      "username": "student100",
      "password": "secret",
      "full_name": "Student One",
      "age": 10,
      "reading_age": 8,
      "learning_style": "general",
      "interests": ["chess"],
      "neuro_profile": ["general"]
    }
    ```

- `GET /api/teacher/students/{student_id}`
  - Role: `teacher`
  - Returns one student.

- `PUT /api/teacher/students/{student_id}`
  - Role: `teacher`
  - Body:
    ```json
    {
      "full_name": "Student One",
      "age": 11,
      "reading_age": 9,
      "learning_style": "visual",
      "interests": ["chess", "football"],
      "neuro_profile": ["adhd"],
      "password": "newpass",
      "is_active": true
    }
    ```

- `GET /api/teacher/students/{student_id}/goals`
  - Role: `teacher`
  - Returns active and archived goals.

- `POST /api/teacher/students/{student_id}/goals`
  - Role: `teacher`
  - Body:
    ```json
    { "goal_text": "Learn handwashing and hygiene basics" }
    ```

- `GET /api/teacher/students/{student_id}/mastery?limit=20&offset=0&concept_key=<optional>`
  - Role: `teacher`
  - Returns mastery event history for a student.

- `GET /api/teacher/students/{student_id}/mastery/stats?recent_days=7`
  - Role: `teacher`
  - Returns aggregate mastery statistics for a student.

- `GET /api/teacher/students/{student_id}/conversations`
  - Role: `teacher`
  - Returns the persisted conversation list for a student.

- `GET /api/teacher/students/{student_id}/conversations/{conversation_id}`
  - Role: `teacher`
  - Returns the persisted conversation with messages.

### Admin - Retriever Config

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

### Admin - System Stats

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

### Admin Flow (curl)

```bash
# Admin login -> create teacher -> list teachers -> update teacher -> retriever config -> system stats
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@neurolearn.local","password":"admin123","role":"admin"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

TEACHER_ID=$(curl -s -X POST http://localhost:8000/api/admin/teachers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"username":"teacher1","password":"secret","full_name":"Teacher One"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['teacher_id'])")

curl -s -X GET http://localhost:8000/api/admin/teachers \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

curl -s -X PUT http://localhost:8000/api/admin/teachers/${TEACHER_ID} \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"full_name":"Teacher One","is_active":true}'

curl -s -X GET http://localhost:8000/api/admin/retriever/config \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"

curl -s -X PATCH http://localhost:8000/api/admin/retriever/config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"candidate_k":25,"min_similarity":0.32,"dedup_max_per_source_page":1,"rerank_enabled":true,"hybrid_enabled":false,"top_k":5}'

curl -s -X GET http://localhost:8000/api/admin/system/stats \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

### Teacher Flow (curl)

```bash
# Teacher login -> create student -> assign goal -> list students -> view student data
TEACHER_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher1","password":"secret","role":"teacher"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

STUDENT_ID="s200"

curl -s -X POST http://localhost:8000/api/teacher/students \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}" \
  -d '{"student_id":"s200","username":"student200","password":"secret","full_name":"Student Two","age":11,"reading_age":9,"learning_style":"visual","interests":["chess"],"neuro_profile":["general"]}'

curl -s -X POST http://localhost:8000/api/teacher/students/${STUDENT_ID}/goals \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TEACHER_TOKEN}" \
  -d '{"goal_text":"Learn handwashing and hygiene basics"}'

curl -s -X GET http://localhost:8000/api/teacher/students \
  -H "Authorization: Bearer ${TEACHER_TOKEN}"

curl -s -X GET http://localhost:8000/api/teacher/students/${STUDENT_ID} \
  -H "Authorization: Bearer ${TEACHER_TOKEN}"

curl -s -X GET http://localhost:8000/api/teacher/students/${STUDENT_ID}/mastery?limit=20 \
  -H "Authorization: Bearer ${TEACHER_TOKEN}"

curl -s -X GET http://localhost:8000/api/teacher/students/${STUDENT_ID}/conversations \
  -H "Authorization: Bearer ${TEACHER_TOKEN}"
```

## Notes

- Tutor conversation history returned by `/api/conversations` may be in-memory and can reset on server restart.
- The tutor requires `GROQ_API_KEY` to initialize the LLM.
- RAG sources are included in `sources` when retrieval is successful.
