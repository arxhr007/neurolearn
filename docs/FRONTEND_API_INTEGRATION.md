# NeuroLearn Frontend API Integration Guide

This document explains how frontend clients (web/mobile) should connect to the NeuroLearn FastAPI backend and use all available endpoints.

## 0. Ready-to-Use TypeScript Client

A single-file typed API wrapper is available at:

- `docs/neurolearn-api-client.ts`

You can copy it into your frontend codebase (for example, `src/lib/api/neurolearn-api-client.ts`) and use it directly.

## 1. Base Connection

- Local base URL: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/api/docs`
- Redoc docs: `http://localhost:8000/api/redoc`

### Required Headers

For authenticated routes:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## 2. Authentication Flow (Frontend)

### 2.1 Login

`POST /api/auth/login`

Request body:

```json
{
  "email": "student@neurolearn.local",
  "password": "student123",
  "role": "student"
}
```

Response body:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "expires_in": 86400,
  "user": {
    "user_id": "user_student_1",
    "email": "student@neurolearn.local",
    "role": "student",
    "name": "Student User",
    "student_id": "s100",
    "cohort_id": null
  }
}
```

Frontend notes:

- Store `access_token` in memory or secure storage.
- Use `refresh_token` to refresh session before expiration.
- Role mismatch returns `403`.

### 2.2 Refresh Token

`POST /api/auth/refresh`

Request body:

```json
{
  "refresh_token": "<jwt>"
}
```

Returns a new access token + refresh token.

### 2.3 Logout

`POST /api/auth/logout`

Requires bearer token. Current implementation is stateless and returns success message.

## 3. Role Access Matrix

- `student`: can use tutor, conversation, read profile/mastery/goals.
- `teacher`: student rights + update student profile + create goals + read admin stats/config.
- `admin`: all teacher rights + update retriever config.

## 4. Tutor Endpoints

### 4.1 Ask a Question

`POST /api/tutor/question`

Request body:

```json
{
  "student_id": "s100",
  "conversation_id": "conv-1",
  "question": "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?",
  "context": {
    "top_k": 5
  }
}
```

Response body (example):

```json
{
  "conversation_id": "conv-1",
  "turn_id": "48b71cd2-fbd0-4125-865b-a130407b237f",
  "answer": "...",
  "check_question": "...",
  "check_answer_hint": "...",
  "sources": [
    {
      "source": "Primary_1.pdf",
      "page": 51,
      "chunk_id": "136",
      "excerpt": "...",
      "distance": 0.18,
      "similarity_score": 0.81
    }
  ],
  "status": "waiting_for_answer",
  "generated_at": "2026-04-13T18:16:17.954907"
}
```

Frontend behavior:

- Save `conversation_id` and `turn_id`.
- If `status=waiting_for_answer`, show `check_question` UI.
- Render sources in expandable citations panel.

### 4.2 Submit Check Answer

`POST /api/tutor/answer`

Request body:

```json
{
  "student_id": "s100",
  "conversation_id": "conv-1",
  "turn_id": "48b71cd2-fbd0-4125-865b-a130407b237f",
  "student_answer": "കൈകൾ വൃത്തിയായി സൂക്ഷിക്കാൻ.",
  "check_answer_hint": "optional"
}
```

Response body:

```json
{
  "conversation_id": "conv-1",
  "turn_id": "48b71cd2-fbd0-4125-865b-a130407b237f",
  "is_correct": true,
  "feedback": "...",
  "misconception": null,
  "confidence": 0.92,
  "mastery_event_id": "123",
  "remediation": null,
  "status": "evaluated",
  "generated_at": "2026-04-13T18:17:10.000000"
}
```

Frontend behavior:

- If `is_correct=false`, show remediation and allow retry.
- If `is_correct=true`, move to next question prompt.

## 5. Conversation Endpoints

### 5.1 Latest Conversation Snapshot

`GET /api/conversations/{student_id}?limit=10`

Returns most recent conversation summary and last turns.

### 5.2 Conversation by ID

`GET /api/conversations/{student_id}/{conversation_id}`

Returns complete in-memory conversation history for that ID.

### 5.3 Clear Conversation

`DELETE /api/conversations/{conversation_id}`

Response:

```json
{ "deleted": true }
```

## 6. Student Profile Endpoints

### 6.1 Get Student Profile

`GET /api/students/{student_id}`

Response:

```json
{
  "student_id": "s100",
  "name": "Test User",
  "learning_style": "analogy-heavy",
  "reading_age": 12,
  "interests": ["hygiene", "health"],
  "neuro_profile": ["general"],
  "created_at": "2026-04-13T18:00:00",
  "updated_at": "2026-04-13T18:00:00"
}
```

### 6.2 Update Student Profile (Teacher/Admin)

`PUT /api/students/{student_id}`

Request body:

```json
{
  "name": "Test User",
  "learning_style": "visual",
  "reading_age": 11,
  "interests": ["science", "football"],
  "neuro_profile": ["adhd"]
}
```

## 7. Mastery Endpoints

### 7.1 Mastery History

`GET /api/students/{student_id}/mastery?limit=20&offset=0&concept_key=<optional>`

Returns:

```json
{
  "total": 1,
  "events": [
    {
      "id": "123",
      "student_id": "s100",
      "concept_key": "hygiene:handwashing",
      "is_correct": true,
      "confidence": 0.92,
      "misconception": null,
      "source_doc": "Primary_1.pdf",
      "source_page": 51,
      "source_chunk_id": 136,
      "created_at": "2026-04-13T18:17:10"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

### 7.2 Mastery Stats

`GET /api/students/{student_id}/mastery/stats?recent_days=7`

Returns aggregate accuracy and event totals.

## 8. Learning Goal Endpoints

### 8.1 Get Goals

`GET /api/students/{student_id}/goals`

Returns:

```json
{
  "active": [
    {
      "goal_id": "4",
      "goal_text": "Learn handwashing basics",
      "is_active": true,
      "created_at": "2026-04-13T17:00:00",
      "updated_at": "2026-04-13T17:00:00"
    }
  ],
  "archived": []
}
```

### 8.2 Create Goal (Teacher/Admin)

`POST /api/students/{student_id}/goals`

Request:

```json
{
  "goal_text": "Learn handwashing basics"
}
```

## 9. Admin Endpoints

### 9.1 Read Retriever Config (Teacher/Admin)

`GET /api/admin/retriever/config`

### 9.2 Update Retriever Config (Admin)

`PATCH /api/admin/retriever/config`

Request body:

```json
{
  "candidate_k": 25,
  "min_similarity": 0.32,
  "dedup_max_per_source_page": 1,
  "rerank_enabled": true,
  "hybrid_enabled": false,
  "top_k": 5,
  "notes": "optional"
}
```

### 9.3 System Stats (Teacher/Admin)

`GET /api/admin/system/stats`

Returns API-level stats including retriever and DB health information.

## 10. Meta Endpoints

- `GET /` -> app info + docs path
- `GET /api/health` -> service health map

## 11. Frontend Integration Example (JavaScript)

```javascript
const API_BASE = "http://localhost:8000";

async function login(email, password, role) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, role }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function askQuestion(token, payload) {
  const res = await fetch(`${API_BASE}/api/tutor/question`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

## 12. Common Errors and Fixes

- `401 Invalid authentication credentials`
Cause: missing/expired token.
Fix: login again or refresh token.

- `403 Insufficient permissions`
Cause: role does not match endpoint access.
Fix: use teacher/admin credentials for privileged routes.

- `404 Student not found: <id>`
Cause: student profile not present in DB.
Fix: create student via `manage_student_db.py` or API update route.

- `503 Tutor service unavailable: missing GROQ_API_KEY`
Cause: API process cannot read env key.
Fix: ensure `.env` has `GROQ_API_KEY` and restart API process.

## 13. Recommended Frontend Call Sequence

1. Login (`/api/auth/login`)
2. Load student profile (`/api/students/{student_id}`)
3. Ask question (`/api/tutor/question`)
4. Display answer + check question + sources
5. Submit student answer (`/api/tutor/answer`)
6. Refresh mastery widget (`/api/students/{student_id}/mastery/stats`)
7. Load history (`/api/conversations/{student_id}/{conversation_id}`)
