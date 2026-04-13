# NeuroLearn Web Product Design

**Status:** Product Specification for Web Migration  
**Last Updated:** April 2026  
**Scope:** Student-facing tutor UI + Admin/teacher dashboard + API contracts

---

## 1. Product Overview

### Vision
Transform NeuroLearn from a CLI-first tool into a dual-surface web platform:
- **Student Tutor**: A chat-like interface where neurodivergent learners interact with the AI tutor, see adaptive explanations, answer check questions, and track mastery progress.
- **Admin Dashboard**: A management portal where teachers and admins create/manage student profiles, set learning goals, monitor mastery events, ingest new content, and review analytics.

### Key Constraints
- Single-VPS MVP deployment (VM with PostgreSQL + Chroma/vector store).
- Keep all existing LangGraph tutoring logic and retrieval pipeline intact.
- Multi-tenant isolation: students only see their own data; admins can manage multiple learners.
- Async/non-blocking requests where possible; long jobs (PDF ingestion, indexing) run in background.

---

## 2. User Roles and Access Control

### Role: Student
- **Who:** A neurodivergent learner accessing the tutor.
- **Auth:** Email/password login or short PIN + device code (for accessibility).
- **Access:**
  - Read: Own profile (learning style, reading age, interests, neuro profile), active learning goals, mastery history, past conversations.
  - Write: Can ask questions, submit answers, update own profile (optionally).
  - Cannot: See other students' data, manage content, view system config.
- **Session:** Browser session with JWT or secure cookie; auto-timeout after inactivity (e.g., 1 hour).

### Role: Teacher / Facilitator
- **Who:** An educator managing a cohort of students (e.g., classroom).
- **Auth:** Email/password login with teacher code or institutional SSO.
- **Access:**
  - Read: All students in their cohort, each student's profile, goals, mastery events, conversation logs.
  - Write: Create/update student profiles, set/update learning goals, add notes/observations.
  - Cannot: Access the admin panel, configure system settings, or manage content indexing.
- **Session:** Same JWT/cookie-based session as students.

### Role: Admin / Content Manager
- **Who:** A system administrator or content curator.
- **Auth:** Email/password with strong enforcement; multi-factor auth recommended.
- **Access:**
  - Read: All data (students, teachers, mastery, logs, system health).
  - Write: Everything. Ingest PDFs, rebuild vector index, adjust retrieval params, manage content sources, export/import data.
  - Special: Health dashboard, job queue status, logs, API key management.
- **Session:** Same auth as others but with additional scope or role claim.

### Access Control Policy
```
┌─────────────┬──────────────┬──────────────┬──────────────┐
│ Resource    │ Student      │ Teacher      │ Admin        │
├─────────────┼──────────────┼──────────────┼──────────────┤
│ Own Profile │ Read/Write   │ Read         │ Read/Write   │
│ Other Prof. │ None         │ Read (cohort)│ Read/Write   │
│ Goals       │ Read (own)   │ Read/Write   │ Read/Write   │
│ Mastery Log │ Read (own)   │ Read (cohort)│ Read/Write   │
│ Conversation│ Read (own)   │ Read (cohort)│ Read/Write   │
│ Content Mgmt│ None         │ None         │ Read/Write   │
│ Settings    │ None         │ None         │ Read/Write   │
└─────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 3. API Specification

### Authentication Endpoints

#### POST /api/auth/login
**Purpose:** Student or teacher login.

**Request:**
```json
{
  "email": "student@example.com",
  "password": "...encrypted or hashed...",
  "role": "student" | "teacher" | "admin"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "user": {
    "user_id": "u123",
    "email": "student@example.com",
    "role": "student",
    "student_id": "s100",
    "name": "Alice"
  },
  "expires_in": 3600
}
```

**Notes:**
- Tokens are short-lived JWT (1 hour); refresh token for extending session.
- Role embedded in token so frontend can decide which UI to show.

---

#### POST /api/auth/refresh
**Purpose:** Refresh access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "expires_in": 3600
}
```

---

#### POST /api/auth/logout
**Purpose:** Invalidate session and refresh token.

**Request:** (empty body, uses Authorization header)

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

---

### Student Tutor Endpoints

#### POST /api/tutor/question
**Purpose:** Send a question to the AI tutor and get an answer with check question (if applicable).

**Request:**
```json
{
  "student_id": "s100",
  "conversation_id": "conv_xyz",
  "question": "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?",
  "context": {
    "active_goal": "Learn handwashing basics",
    "recent_mastery": ["handwashing:page_number"]
  }
}
```

**Response:**
```json
{
  "conversation_id": "conv_xyz",
  "turn_id": "turn_001",
  "answer": "കൈകഴുകൽ വളരെ പ്രധാനമാണ്...",
  "check_question": "കൈകഴുകാൻ എന്തു ഉപയോഗിക്കുന്നു?",
  "check_answer_hint": "സോപ്പും നൂറ്റാണ്ടും",
  "sources": [
    {
      "source": "Care group.pdf",
      "page": 5,
      "chunk_id": "chunk_42",
      "excerpt": "കൈകഴുകൽ ശരിയായി വിശദീകരിക്കുന്നു..."
    }
  ],
  "status": "waiting_for_answer",
  "generated_at": "2026-04-13T10:30:00Z"
}
```

**Notes:**
- Conversation ID groups multi-turn interactions; can be "new" for first turn.
- Sources include location hints so student can look up in the textbook if needed.
- Status indicates tutor state: `waiting_for_answer`, `answered`, `error`.

---

#### POST /api/tutor/answer
**Purpose:** Submit student answer to a check question; get evaluation and next steps.

**Request:**
```json
{
  "student_id": "s100",
  "conversation_id": "conv_xyz",
  "turn_id": "turn_001",
  "student_answer": "സോപ്പ് മാത്രം",
  "check_answer_hint": "സോപ്പും നൂറ്റാണ്ടും"
}
```

**Response:**
```json
{
  "conversation_id": "conv_xyz",
  "turn_id": "turn_001",
  "is_correct": false,
  "feedback": "ഭാഗികമായി ശരി. നൂറ്റിനെപ്പറ്റിയും സാരമായിരുന്നു...",
  "misconception": "നൂറ്റിന്റെ പ്രാധാന്യമെന്തെന്ന് മനസ്സിലാകാത്തത്",
  "confidence": 0.85,
  "mastery_event_id": "me_789",
  "remediation": "നൂറ്റ് ഉപയോഗിച്ച് കൈ ഉണങ്ങാൻ സഹായിക്കുന്നത്...",
  "status": "evaluated",
  "generated_at": "2026-04-13T10:31:00Z"
}
```

**Notes:**
- `is_correct` + `confidence` feeds profile update logic server-side.
- Remediation provided if answer is incorrect; no second check question within same turn.
- Mastery event persisted; ID returned for audit.

---

#### GET /api/tutor/conversation/{conversation_id}
**Purpose:** Retrieve a past conversation (multi-turn chat history).

**Response:**
```json
{
  "conversation_id": "conv_xyz",
  "student_id": "s100",
  "created_at": "2026-04-13T10:00:00Z",
  "updated_at": "2026-04-13T10:35:00Z",
  "turns": [
    {
      "turn_id": "turn_001",
      "type": "question",
      "question": "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?",
      "answer": "കൈകഴുകൽ വളരെ പ്രധാനമാണ്...",
      "sources": [...]
    },
    {
      "turn_id": "turn_001",
      "type": "answer",
      "student_answer": "സോപ്പ് മാത്രം",
      "is_correct": false,
      "feedback": "ഭാഗികമായി ശരി..."
    },
    {
      "turn_id": "turn_002",
      "type": "question",
      "question": "അതെന്തുകൊണ്ട് പ്രധാനമാണ്?",
      "answer": "...",
      "status": "answered"
    }
  ],
  "learning_goal": "Learn handwashing basics"
}
```

---

### Student Profile Endpoints

#### GET /api/students/{student_id}/profile
**Purpose:** Fetch the current student profile.

**Response:**
```json
{
  "student_id": "s100",
  "name": "Alice",
  "learning_style": "analogy-heavy",
  "reading_age": 12,
  "interests": ["chess", "football"],
  "neuro_profile": ["adhd", "dyslexia"],
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-04-13T08:00:00Z"
}
```

**Access:** Student can GET own; teacher/admin can GET any in cohort/all.

---

#### PATCH /api/students/{student_id}/profile
**Purpose:** Update student profile (learning style, interests, etc.).

**Request:**
```json
{
  "learning_style": "visual",
  "reading_age": 13,
  "interests": ["chess", "art", "music"]
}
```

**Response:** Updated profile object.

**Access:** Student can PATCH own; teacher/admin can PATCH any (with audit trail).

---

### Learning Goals Endpoints

#### GET /api/students/{student_id}/goals
**Purpose:** List all learning goals for a student (active and archived).

**Response:**
```json
{
  "active": [
    {
      "goal_id": "goal_1",
      "goal_text": "Learn handwashing basics",
      "created_at": "2026-04-10T00:00:00Z",
      "updated_at": "2026-04-13T00:00:00Z",
      "progress": 0.6,
      "mastery_count": 3
    }
  ],
  "archived": [
    {
      "goal_id": "goal_0",
      "goal_text": "Learn greeting protocols",
      "completed_at": "2026-04-09T00:00:00Z"
    }
  ]
}
```

---

#### POST /api/students/{student_id}/goals
**Purpose:** Create a new learning goal.

**Request:**
```json
{
  "goal_text": "Learn food safety basics"
}
```

**Response:**
```json
{
  "goal_id": "goal_2",
  "goal_text": "Learn food safety basics",
  "is_active": true,
  "created_at": "2026-04-13T10:00:00Z"
}
```

**Access:** Teacher/admin only; creates goal for a student.

---

#### PATCH /api/students/{student_id}/goals/{goal_id}
**Purpose:** Update goal text or mark as complete/active.

**Request:**
```json
{
  "goal_text": "Learn food safety and hygiene",
  "is_active": false
}
```

**Response:** Updated goal object.

---

#### DELETE /api/students/{student_id}/goals/{goal_id}
**Purpose:** Archive a goal (soft delete).

**Response:**
```json
{
  "message": "Goal archived successfully"
}
```

---

### Mastery Endpoints

#### GET /api/students/{student_id}/mastery
**Purpose:** Fetch mastery event history with optional filtering.

**Query Params:**
- `limit=20` — number of recent events.
- `concept_key=handwashing` — filter by concept.
- `offset=0` — pagination.

**Response:**
```json
{
  "total": 42,
  "events": [
    {
      "id": "me_789",
      "student_id": "s100",
      "concept_key": "handwashing:hygiene_importance",
      "is_correct": true,
      "confidence": 0.92,
      "misconception": null,
      "source_doc": "Care group.pdf",
      "source_page": 5,
      "created_at": "2026-04-13T10:31:00Z"
    },
    {
      "id": "me_788",
      "student_id": "s100",
      "concept_key": "handwashing:hygiene_importance",
      "is_correct": false,
      "confidence": 0.85,
      "misconception": "Does not understand why soap + water is needed",
      "source_doc": "Care group.pdf",
      "source_page": 5,
      "created_at": "2026-04-13T10:25:00Z"
    }
  ]
}
```

**Access:** Student can GET own; teacher/admin can GET any student's mastery.

---

### Admin Content Management Endpoints

#### GET /api/admin/content/status
**Purpose:** Check current vector index and PDF ingestion status.

**Response:**
```json
{
  "vector_store": {
    "type": "chroma",
    "chunk_count": 1250,
    "collection_name": "malayalam_rag",
    "size_mb": 45.2,
    "last_rebuilt": "2026-04-10T14:30:00Z"
  },
  "ingestion_jobs": [
    {
      "job_id": "job_5",
      "status": "in_progress",
      "pdf_file": "Care group.pdf",
      "progress_percent": 75,
      "started_at": "2026-04-13T09:00:00Z",
      "eta": "2026-04-13T09:45:00Z"
    },
    {
      "job_id": "job_4",
      "status": "completed",
      "pdf_file": "Primary.pdf",
      "chunks_generated": 123,
      "completed_at": "2026-04-12T20:00:00Z"
    }
  ]
}
```

**Access:** Admin only.

---

#### POST /api/admin/content/ingest
**Purpose:** Trigger PDF ingestion pipeline for uploaded content.

**Request (multipart/form-data):**
```
pdf_file: <File>
chunk_size: 500
chunk_overlap: 100
workers: 4
```

**Response:**
```json
{
  "job_id": "job_6",
  "status": "queued",
  "pdf_file": "NewContent.pdf",
  "created_at": "2026-04-13T10:45:00Z",
  "message": "PDF ingestion queued. Check status with GET /api/admin/content/status"
}
```

**Notes:**
- Runs asynchronously in background worker.
- Returns job ID for polling or webhook callback.

---

#### POST /api/admin/content/rebuild-index
**Purpose:** Rebuild the vector index from all currently ingested chunks.

**Request:**
```json
{
  "force": true,
  "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
}
```

**Response:**
```json
{
  "job_id": "job_7",
  "status": "in_progress",
  "estimated_duration_seconds": 300,
  "message": "Vector index rebuild started"
}
```

**Notes:**
- Blocks new tutor requests during rebuild (or queues them).
- Can be triggered on a schedule or manually.

---

#### GET /api/admin/retrieval-config
**Purpose:** Get and preview current retrieval tuning parameters.

**Response:**
```json
{
  "candidate_k": 25,
  "min_similarity": 0.32,
  "dedup_max_per_source_page": 1,
  "rerank_enabled": true,
  "hybrid_enabled": false,
  "top_k": 5,
  "notes": "Current production settings optimized for Malayalam queries"
}
```

---

#### PATCH /api/admin/retrieval-config
**Purpose:** Update retrieval tuning (takes effect on next query).

**Request:**
```json
{
  "min_similarity": 0.35,
  "hybrid_enabled": true
}
```

**Response:** Updated config object.

**Notes:**
- Changes apply to subsequent requests; no cache invalidation needed.

---

### Admin User / Teacher Management Endpoints

#### GET /api/admin/users
**Purpose:** List all users (students, teachers, admins) with roles and cohort info.

**Query Params:**
- `role=student|teacher|admin`
- `cohort_id=cohort_1`

**Response:**
```json
{
  "total": 87,
  "users": [
    {
      "user_id": "u100",
      "email": "alice@school.edu",
      "role": "student",
      "student_id": "s100",
      "name": "Alice",
      "cohort_id": "class_4b",
      "created_at": "2026-01-15T00:00:00Z"
    },
    {
      "user_id": "u200",
      "email": "mr_smith@school.edu",
      "role": "teacher",
      "name": "Mr. Smith",
      "cohort_id": "class_4b",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

**Access:** Admin only.

---

#### POST /api/admin/users
**Purpose:** Create a new user (student, teacher, or admin).

**Request:**
```json
{
  "email": "new_student@school.edu",
  "password": "...",
  "role": "student",
  "name": "Bobby",
  "cohort_id": "class_4b",
  "student_profile": {
    "learning_style": "visual",
    "reading_age": 11,
    "interests": ["art"],
    "neuro_profile": ["dyslexia"]
  }
}
```

**Response:**
```json
{
  "user_id": "u301",
  "email": "new_student@school.edu",
  "role": "student",
  "student_id": "s301",
  "name": "Bobby",
  "created_at": "2026-04-13T11:00:00Z"
}
```

**Access:** Admin only.

---

#### DELETE /api/admin/users/{user_id}
**Purpose:** Deactivate a user (soft delete).

**Response:**
```json
{
  "message": "User deactivated successfully"
}
```

---

### Health & Analytics Endpoints

#### GET /api/health
**Purpose:** System health check (no auth required).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-13T11:00:00Z",
  "services": {
    "api": "ok",
    "database": "ok",
    "vector_store": "ok",
    "llm_provider": "ok"
  }
}
```

---

#### GET /api/admin/analytics
**Purpose:** High-level analytics (admin only).

**Query Params:**
- `period=7d|30d|90d`
- `group_by=student|cohort|concept`

**Response:**
```json
{
  "period": "7d",
  "total_students": 42,
  "active_students_7d": 28,
  "total_conversations": 312,
  "total_mastery_events": 1840,
  "avg_accuracy": 0.74,
  "top_concepts": [
    {
      "concept": "handwashing:hygiene_importance",
      "events": 45,
      "accuracy": 0.81
    }
  ],
  "cohort_performance": [
    {
      "cohort_id": "class_4a",
      "students": 20,
      "avg_accuracy": 0.76
    }
  ]
}
```

---

## 4. Frontend Architecture

### Overview
```
┌────────────────────────────────────────────────────────────────┐
│                         Frontend (React/Vue)                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────┐     ┌──────────────────────────────┐ │
│  │  Student Tutor UI   │     │  Admin Dashboard             │ │
│  │  ├─ Chat Window     │     │  ├─ Student Manager          │ │
│  │  ├─ Answer Form     │     │  ├─ Goal Manager             │ │
│  │  ├─ Sources List    │     │  ├─ Mastery Viewer           │ │
│  │  ├─ Progress Bar    │     │  ├─ Content Ingestion        │ │
│  │  └─ Session Menu    │     │  ├─ Analytics              │ │
│  │                     │     │  └─ Settings                 │ │
│  └─────────────────────┘     └──────────────────────────────┘ │
│           │                              │                     │
│           └──────────────┬───────────────┘                     │
│                          ▼                                     │
│                  ┌───────────────┐                            │
│                  │  Auth Layer   │                            │
│                  │  (JWT/Cookie) │                            │
│                  └───────────────┘                            │
│                          │                                     │
│           ┌──────────────┴──────────────┐                     │
│           ▼                             ▼                     │
│     ┌──────────────┐           ┌──────────────┐             │
│     │  API Client  │           │ Local State  │             │
│     │  (axios)     │           │ (Redux/Pinia)             │
│     └──────────────┘           └──────────────┘             │
│           │                             │                     │
└───────────┼─────────────────────────────┼─────────────────────┘
            │                             │
         HTTP/S                    Session Context
            │                             │
            ▼                             │
      ┌─────────────────────────────────┘
      │
      │  FastAPI Backend
      ├─ /api/auth/*
      ├─ /api/tutor/*
      ├─ /api/students/*
      ├─ /api/admin/*
      └─ /api/health
```

### State Management

**Global State (Redux / Pinia):**
```javascript
{
  auth: {
    access_token,
    refresh_token,
    user_id,
    role,
    student_id (if role=student),
    expires_at
  },
  
  student_profile: {
    student_id,
    name,
    learning_style,
    reading_age,
    interests,
    neuro_profile,
    updated_at
  },

  tutor_session: {
    student_id,
    current_conversation_id,
    current_turn_id,
    pending_check_question,
    pending_check_answer_hint,
    waiting_for_response,
    error (if any)
  },

  ui: {
    sidebar_open,
    current_page (tutor | profile | goals | mastery | admin),
    loading_states: {
      sending_question,
      submitting_answer,
      fetching_profile,
      ...
    }
  },

  admin: {
    selected_student_id (if in teacher/admin mode),
    filter_role,
    filter_cohort,
    content_status (ingestion jobs, vector store info),
    retrieval_config
  }
}
```

---

### Key Frontend Logic

#### 1. Authentication Flow

```
┌─────────────┐
│   Login     │
│   Screen    │
└──────┬──────┘
       │ [email, password] POST /api/auth/login
       ▼
┌──────────────────────┐
│ Receive JWT tokens   │
│ + user info          │
└──────┬───────────────┘
       │ Store in sessionStorage / secure cookie
       │ Store in Redux
       ▼
┌──────────────────────┐
│ Check user role      │
└──────┬───────────────┘
       │
    ┌──┴──┬──────┐
    ▼     ▼      ▼
[Student] [Teacher] [Admin]
    │        │        │
    ▼        ▼        ▼
[Student UI] [Teacher Dashboard] [Admin Dashboard]
```

**Code Flow:**
1. User enters email/password on login form.
2. Frontend POST to `/api/auth/login`.
3. Backend validates, returns `access_token`, `refresh_token`, user metadata.
4. Frontend stores tokens in secure storage and Redux state.
5. Redux state change triggers route guard, loads appropriate UI surface based on role.
6. All subsequent requests include `Authorization: Bearer <access_token>`.
7. On token expiration, middleware calls `/api/auth/refresh` to get new token.

---

#### 2. Student Tutor Chat Flow

```
┌──────────────────────────┐
│ Chat Window Rendered     │
│ (Conversation History +  │
│  Input Box)              │
└──────────┬───────────────┘
           │
  [Student Types Question]
           │
           ▼
┌──────────────────────────┐
│ User Submits Question    │
│ Set UI state:            │
│ waiting_for_response=true│
└──────────┬───────────────┘
           │
           │ POST /api/tutor/question
           │ {
           │   student_id, conversation_id,
           │   question, context
           │ }
           ▼
┌──────────────────────────────────┐
│ Backend Runs LangGraph           │
│ ├─ Intent Classifier             │
│ ├─ Goal Drift Checker            │
│ ├─ Retriever (for context)       │
│ ├─ Personalizer                  │
│ └─ Evaluator (generates check Q) │
└──────────┬──────────────────────┘
           │
           ▼
┌──────────────────────────┐
│ Response Received        │
│ {                        │
│   answer,                │
│   check_question,        │
│   sources,               │
│   status                 │
│ }                        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Render Answer + Sources  │
│ Show Check Question      │
│ Set UI state:            │
│ pending_check_question   │
│ waiting_for_response=false
└──────────┬───────────────┘
           │
  [Student Reads & Answers]
           │
           ▼
┌──────────────────────────┐
│ User Submits Answer      │
│ Set UI state:            │
│ waiting_for_response=true│
└──────────┬───────────────┘
           │
           │ POST /api/tutor/answer
           │ {
           │   student_id, conversation_id,
           │   student_answer, check_answer_hint
           │ }
           ▼
┌──────────────────────────────────┐
│ Backend Evaluates Answer         │
│ ├─ compare with hint              │
│ ├─ LLM scoring                    │
│ ├─ Store mastery event            │
│ └─ (optionally) trigger profile   │
│    update if multi-event pattern  │
└──────────┬──────────────────────┘
           │
           ▼
┌──────────────────────────┐
│ Response Received        │
│ {                        │
│   is_correct,            │
│   feedback,              │
│   misconception,         │
│   remediation (if wrong),│
│   mastery_event_id       │
│ }                        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ If is_correct=true:      │
│  ├─ Show positive        │
│  │  feedback             │
│  └─ Clear pending Q      │
│                          │
│ If is_correct=false:     │
│  ├─ Show remediation     │
│  ├─ Disable answer form  │
│  └─ Optionally offer new │
│     concept or retry     │
└──────────┬───────────────┘
           │
  [User Can Ask New Question Or Explore More]
           │
           ▼
      [Loop Back To Chat]
```

**Frontend Logic Details:**

```javascript
// React Hook Example (Pseudo-code)
function StudentTutorChat() {
  const [conversation, setConversation] = useState([]);
  const [waitingForAnswer, setWaitingForAnswer] = useState(false);
  const [currentCheckQuestion, setCurrentCheckQuestion] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const handleSendQuestion = async (questionText) => {
    setWaitingForAnswer(true);
    setErrorMsg(null);
    try {
      const response = await apiClient.post('/api/tutor/question', {
        student_id: currentStudentId,
        conversation_id: currentConversationId,
        question: questionText,
      });
      
      setConversation(prev => [...prev, {
        type: 'question',
        text: questionText,
        generated_at: new Date()
      }, {
        type: 'answer',
        text: response.data.answer,
        sources: response.data.sources,
        generated_at: response.data.generated_at
      }]);

      if (response.data.check_question) {
        setCurrentCheckQuestion({
          question: response.data.check_question,
          hint: response.data.check_answer_hint,
          turnId: response.data.turn_id
        });
      }
    } catch (error) {
      setErrorMsg(error.message);
    } finally {
      setWaitingForAnswer(false);
    }
  };

  const handleSubmitAnswer = async (answerText) => {
    setWaitingForAnswer(true);
    try {
      const response = await apiClient.post('/api/tutor/answer', {
        student_id: currentStudentId,
        conversation_id: currentConversationId,
        turn_id: currentCheckQuestion.turnId,
        student_answer: answerText,
        check_answer_hint: currentCheckQuestion.hint
      });

      const evaluationMessage = response.data.is_correct
        ? `✓ Correct! ${response.data.feedback}`
        : `✗ Not quite. ${response.data.feedback}`;

      setConversation(prev => [...prev, {
        type: 'student_answer',
        text: answerText,
        is_correct: response.data.is_correct,
        feedback: evaluationMessage
      }]);

      if (response.data.remediation) {
        setConversation(prev => [...prev, {
          type: 'remediation',
          text: response.data.remediation
        }]);
      }

      setCurrentCheckQuestion(null); // Clear pending check question
    } catch (error) {
      setErrorMsg(error.message);
    } finally {
      setWaitingForAnswer(false);
    }
  };

  return (
    <div>
      <ChatHistory messages={conversation} />
      {currentCheckQuestion ? (
        <CheckQuestionForm 
          question={currentCheckQuestion.question}
          onSubmit={handleSubmitAnswer}
          disabled={waitingForAnswer}
        />
      ) : (
        <ChatInput 
          onSend={handleSendQuestion}
          disabled={waitingForAnswer}
        />
      )}
      {errorMsg && <ErrorAlert message={errorMsg} />}
    </div>
  );
}
```

---

#### 3. Admin Dashboard Flow

```
┌────────────────────────┐
│ Admin Logs In          │
│ (via /api/auth/login   │
│  with role=admin)      │
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│ Admin Dashboard        │
│ Sidebar Menu:          │
│ ├─ Students            │
│ ├─ Cohorts             │
│ ├─ Content / Ingestion │
│ ├─ Retrieval Config    │
│ ├─ Analytics           │
│ └─ Settings            │
└────────────┬───────────┘
             │
    [Admin Clicks "Students"]
             │
             ▼
┌────────────────────────────────────┐
│ GET /api/admin/users?role=student  │
│ Display student list with:         │
│ ├─ Name, email, cohort             │
│ ├─ Last active timestamp           │
│ ├─ Action buttons: view, edit,     │
│   delete, set goal                 │
└────────────┬──────────────────────┘
             │
    [Admin Clicks "Edit" on a Student]
             │
             ▼
┌──────────────────────────────────────┐
│ Load Student Profile                 │
│ GET /api/students/{student_id}/      │
│   profile, goals, mastery            │
│                                      │
│ Display Edit Form:                   │
│ ├─ Name, learning_style              │
│ ├─ Reading age, interests             │
│ ├─ Neuro profile (checkboxes)        │
│ └─ Save Button                       │
└────────────┬─────────────────────────┘
             │
    [Admin Modifies & Saves]
             │
             ▼
┌──────────────────────────────────────┐
│ PATCH /api/students/{student_id}/    │
│   profile                            │
│ With updated fields                  │
│                                      │
│ Show success confirmation            │
└────────────┬─────────────────────────┘
             │
    [Admin Clicks "Content Ingestion"]
             │
             ▼
┌─────────────────────────────────────┐
│ GET /api/admin/content/status       │
│ Display:                            │
│ ├─ Vector store info                │
│ ├─ Current ingestion jobs           │
│ ├─ Upload form (drag-drop PDF)      │
│ └─ Rebuild Index button             │
└────────────┬────────────────────────┘
             │
    [Admin Uploads PDF]
             │
             ▼
┌────────────────────────────────────┐
│ POST /api/admin/content/ingest      │
│ (multipart/form-data)               │
│ With PDF file + chunk settings      │
│                                     │
│ Response: job_id, status=queued     │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Use WebSocket or polling            │
│ to monitor job progress             │
│ GET /api/admin/content/status       │
│ (repeat every 2 seconds)            │
│                                     │
│ UI updates with progress bar        │
└────────────┬───────────────────────┘
             │
    [Job completes or fails]
             │
             ▼
┌────────────────────────────────────┐
│ POST /api/admin/content/rebuild-    │
│   index                             │
│ (if needed)                         │
│                                     │
│ Monitor rebuild progress            │
└────────────┬───────────────────────┘
             │
    [Admin Can Now Check Analytics]
             │
             ▼
┌────────────────────────────────────┐
│ GET /api/admin/analytics?period=7d │
│ Display:                           │
│ ├─ Total students, active count    │
│ ├─ Mastery accuracy trends         │
│ ├─ Top concepts by mastery events  │
│ ├─ Cohort performance comparison   │
│ └─ Charts / export buttons         │
└────────────────────────────────────┘
```

---

## 5. Data Models

### Core TypedDicts / Pydantic Models

**Student Profile**
```python
class StudentProfile(BaseModel):
    student_id: str
    name: str
    learning_style: str  # "analogy-heavy", "visual", "kinesthetic", etc.
    reading_age: int  # 6–18
    interests: List[str]  # ["chess", "football"]
    neuro_profile: List[str]  # ["adhd", "dyslexia", "autism", "general"]
    created_at: datetime
    updated_at: datetime
```

**Learning Goal**
```python
class LearningGoal(BaseModel):
    goal_id: str
    student_id: str
    goal_text: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

**Mastery Event**
```python
class MasteryEvent(BaseModel):
    id: str
    student_id: str
    concept_key: str  # "handwashing:hygiene_importance"
    is_correct: bool
    confidence: float  # 0.0 – 1.0
    misconception: Optional[str]
    source_doc: str  # "Care group.pdf"
    source_page: int
    source_chunk_id: int
    created_at: datetime
```

**Conversation**
```python
class Conversation(BaseModel):
    conversation_id: str
    student_id: str
    learning_goal_id: Optional[str]
    turns: List[Turn]
    created_at: datetime
    updated_at: datetime
```

**Turn** (a single question-answer pair or just a question)
```python
class Turn(BaseModel):
    turn_id: str
    type: Literal["question", "answer", "remediation"]
    
    # If type=question
    question: Optional[str]
    answer: Optional[str]
    check_question: Optional[str]
    check_answer_hint: Optional[str]
    sources: Optional[List[Source]]
    
    # If type=answer
    student_answer: Optional[str]
    is_correct: Optional[bool]
    feedback: Optional[str]
    misconception: Optional[str]
    confidence: Optional[float]
    mastery_event_id: Optional[str]
    remediation: Optional[str]
    
    generated_at: datetime
```

**Source** (evidence chunk)
```python
class Source(BaseModel):
    source: str  # "Care group.pdf"
    page: int
    chunk_id: str
    excerpt: str
    distance: Optional[float]  # retrieval score, for observability
```

**Ingestion Job**
```python
class IngestionJob(BaseModel):
    job_id: str
    status: Literal["queued", "in_progress", "completed", "failed"]
    pdf_file: str
    progress_percent: int  # 0–100
    chunks_generated: int
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    eta: Optional[datetime]
```

---

## 6. User Flows

### Flow 1: Student First Login & Learning

**Goal:** A new student logs in, sees the tutor, and answers their first question.

```
1. Student receives login link (email or in-class distribution)
2. Student enters email + temporary password
3. System creates session
4. Student is prompted to set up profile (optional; can skip)
   ├─ Name
   ├─ Learning style (visual, kinesthetic, etc.)
   ├─ Reading age
   └─ Interests
5. Student lands on tutor home screen
6. Student sees active learning goal OR message to set one
7. Student types a question (e.g., "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?")
8. System retrieves answer from LangGraph tutor
9. Student sees answer + check question
10. Student answers check question
11. System evaluates and shows feedback
12. Mastery event recorded in database
13. Student can ask a new question or review sources
```

---

### Flow 2: Teacher Manages Student Goals

**Goal:** A teacher creates a new learning goal for a student mid-cohort.

```
1. Teacher logs in as "teacher"
2. Teacher clicks "Students" in sidebar
3. Teacher sees list of assigned students
4. Teacher clicks "Edit" on Alice's profile
5. Teacher clicks "Add Goal" button
6. Teacher enters goal text: "Learn food safety"
7. Teacher clicks "Save"
8. System POST to /api/students/{student_id}/goals
9. New goal appears in Alice's tutor UI
10. Next time Alice logs in, she sees the new goal as active
11. Alice's first question will be checked against alignment with "food safety"
```

---

### Flow 3: Admin Ingests New Content

**Goal:** An admin uploads a new PDF textbook and rebuilds the vector index.

```
1. Admin logs in as "admin"
2. Admin clicks "Content Ingestion" in sidebar
3. Admin sees current vector store info + list of jobs
4. Admin drags a PDF file onto the upload box
5. Admin optionally adjusts chunk size, overlap, worker count
6. Admin clicks "Upload"
7. System queues ingestion job
8. Admin sees job_id in the list with status "queued"
9. Job runner (background worker) picks up job
   ├─ Extracts text from PDF
   ├─ Chunks the text
   └─ Saves chunks to output/rag_chunks/
10. Admin monitors progress via polling (or WebSocket)
11. Job transitions to "completed" with chunk count
12. Admin clicks "Rebuild Index"
13. System queues index rebuild job
14. Index builder loads all chunks from output/ into Chroma
15. Admin sees vector store chunk count increase
16. All subsequent tutor queries now use the new chunks
```

---

### Flow 4: Teacher Views Student Mastery

**Goal:** A teacher inspects a student's progress to decide on next steps.

```
1. Teacher logs in and clicks "Students"
2. Teacher finds Alice in the list
3. Teacher clicks "View Mastery"
4. System GET /api/students/{student_id}/mastery
5. Teacher sees timeline of mastery events:
   ├─ Concept, date, is_correct, confidence
   ├─ Misconceptions noted (if any)
   └─ Source document links
6. Teacher filters by concept or date range
7. Teacher notices Alice struggles with "food:contamination"
8. Teacher clicks "Set Goal" on Alice to focus on that topic
9. System updates Alice's learning goal
10. Next tutor interaction will drift-check against the new goal
```

---

## 7. Frontend Component Structure

### Student UI (React Components Example)

```
StudentApp/
├─ Layout/
│  ├─ Navbar (logout, profile menu)
│  ├─ Sidebar (nav links: Chat, Goals, Progress, Settings)
│  └─ Footer (help, feedback)
├─ Pages/
│  ├─ ChatPage/
│  │  ├─ ChatWindow (conversation history)
│  │  ├─ InputBox (question input)
│  │  ├─ CheckQuestionForm (answer input)
│  │  ├─ SourceLink (expandable source citation)
│  │  └─ hooks/
│  │     ├─ useTutorChat (manage question/answer flow)
│  │     └─ useConversationHistory (load past chats)
│  ├─ ProfilePage/
│  │  ├─ ProfileCard (display current profile)
│  │  ├─ EditProfileForm (update learning style, interests)
│  │  └─ hooks/
│  │     └─ useStudentProfile (fetch/update profile)
│  ├─ GoalsPage/
│  │  ├─ ActiveGoals (list current goal + progress)
│  │  ├─ ArchivedGoals (past goals)
│  │  └─ hooks/
│  │     └─ useStudentGoals (fetch/manage goals)
│  ├─ MasteryPage/
│  │  ├─ MasteryTimeline (chronological event list)
│  │  ├─ ConceptSummary (group events by concept)
│  │  ├─ MasteryChart (accuracy over time)
│  │  └─ hooks/
│  │     └─ useMasteryHistory (fetch mastery events)
│  └─ SettingsPage/
│     ├─ ChangePassword
│     ├─ NotificationPrefs
│     └─ LogoutButton
├─ Shared/
│  ├─ ProtectedRoute (checks auth before rendering)
│  ├─ FallbackLoader (loading spinner)
│  ├─ ErrorBoundary (catch React errors)
│  ├─ NotificationCenter (toast notifications)
│  └─ hooks/
│     ├─ useAuth (access token, refresh, logout)
│     ├─ useApiClient (HTTP client with auto-retry)
│     └─ useLocalStorage (session persistence)
└─ store/
   ├─ auth.slice.js (Redux or Pinia)
   ├─ tutor_session.slice.js
   ├─ student_profile.slice.js
   └─ ui.slice.js

```

### Admin/Teacher Dashboard (React Components Example)

```
AdminDashboard/
├─ Layout/
│  ├─ Navbar (admin badges, logout)
│  ├─ Sidebar (nav: Students, Cohorts, Content, Analytics, Settings)
│  └─ BreadcrumbNav
├─ Pages/
│  ├─ StudentManagementPage/
│  │  ├─ StudentTable (list, sort, filter, search)
│  │  ├─ StudentRecord (detail view)
│  │  ├─ EditStudentForm
│  │  ├─ ConfirmDeleteModal
│  │  └─ hooks/
│  │     └─ useStudentCRUD (create, read, update, delete)
│  ├─ ContentPage/
│  │  ├─ VectorStoreStatus (chunk count, size, last rebuild)
│  │  ├─ IngestionJobList (monitor active/past jobs)
│  │  ├─ UploadDropZone (drag-drop PDF upload)
│  │  ├─ RebuildIndexButton
│  │  ├─ UploadProgressBar (show job progress)
│  │  └─ hooks/
│  │     ├─ useIngestionJobs (poll status)
│  │     └─ useContentUpload (handle file upload)
│  ├─ RetrieverConfigPage/
│  │  ├─ ConfigForm (min_similarity, candidate_k, etc.)
│  │  ├─ PreviewButton (test current config)
│  │  └─ hooks/
│  │     └─ useRetrieverConfig (fetch/update config)
│  ├─ AnalyticsPage/
│  │  ├─ MetricsCard (total students, active, avg accuracy)
│  │  ├─ AccuracyTrendChart (line chart over time)
│  │  ├─ TopConceptsTable (concepts by mastery event count)
│  │  ├─ CohortComparisonChart (cohort performance)
│  │  ├─ ExportButton (CSV, JSON export)
│  │  └─ hooks/
│  │     └─ useAnalytics (fetch analytics data)
│  └─ SettingsPage/
│     ├─ SystemSettings
│     ├─ CohortManagement
│     ├─ UsersManagement (create admin, teacher)
│     └─ BackupControls
├─ Shared/
│  ├─ AdminProtectedRoute (checks role=admin)
│  ├─ Table (reusable data table with pagination)
│  ├─ Modal (dialog component)
│  ├─ Form (form input utilities)
│  ├─ Chart (charts wrapper)
│  └─ hooks/
│     ├─ useAdminAuth (role-based access)
│     └─ useDataTable (pagination, sort, filter state)
└─ store/
   ├─ admin_users.slice.js
   ├─ content_jobs.slice.js
   ├─ analytics.slice.js
   └─ admin_ui.slice.js
```

---

## 8. Error Handling & Edge Cases

### API Error Responses

All endpoints return consistent error format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Question text is empty",
    "details": {
      "field": "question",
      "reason": "required"
    },
    "request_id": "req_abc123"
  }
}
```

**Common Error Codes:**
- `UNAUTHORIZED` (401) — Missing/invalid token.
- `FORBIDDEN` (403) — User lacks permission.
- `NOT_FOUND` (404) — Resource does not exist.
- `INVALID_REQUEST` (400) — Bad input.
- `CONFLICT` (409) — Resource already exists.
- `RATE_LIMIT_EXCEEDED` (429) — Too many requests.
- `INTERNAL_SERVER_ERROR` (500) — Server-side fault.

---

### Frontend Error Handling

```javascript
// API client with retry + refresh logic
const apiClient = axios.create({
  baseURL: 'https://api.neurolearn.com',
  timeout: 30000,
});

apiClient.interceptors.response.use(
  response => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and not already retried, refresh token and retry
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const { data } = await axios.post('/api/auth/refresh', {
          refresh_token: store.getState().auth.refresh_token
        });
        store.dispatch(setAccessToken(data.access_token));
        originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed; redirect to login
        store.dispatch(logout());
        return Promise.reject(refreshError);
      }
    }

    // 403 — permission denied
    if (error.response?.status === 403) {
      showNotification('error', 'You do not have permission to perform this action.');
      return Promise.reject(error);
    }

    // 429 — rate limit
    if (error.response?.status === 429) {
      showNotification('error', 'Too many requests. Please wait before trying again.');
      return Promise.reject(error);
    }

    // Other 4xx or 5xx
    if (error.response?.status >= 400) {
      const msg = error.response?.data?.error?.message || 'An error occurred.';
      showNotification('error', msg);
      return Promise.reject(error);
    }

    // Network or timeout
    showNotification('error', 'Connection error. Please check your network.');
    return Promise.reject(error);
  }
);
```

---

### Edge Cases

1. **Student loses internet mid-answer:** Frontend queues the answer locally; on reconnect, retry the request.
2. **Tutor LLM times out:** Return 504 with "Please try again" message; frontend offers a "Retry" button.
3. **Vector store is offline during rebuild:** Incoming tutor requests are queued briefly; if not resolved, return error to user.
4. **Student updates profile while tutoring:** Profile changes apply to next conversation turn, not mid-conversation.
5. **Teacher deletes student during session:** Student session invalidated; user logged out with "Your profile was deleted" message.
6. **Admin modifies retrieval config during inference:** Changes apply to next query, not inflight requests.

---

## 9. Deployment Targets & Infrastructure

### Single VPS Deployment (MVP)

```
┌─────────────────────────────────────────────────────┐
│                   VPS (1 machine)                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Nginx / Reverse Proxy (Port 443 TLS)         │  │
│  │ ├─ Route /api/* → API Backend                │  │
│  │ └─ Route /*     → React Frontend SPA          │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ FastAPI Backend (Port 8000, internal)        │  │
│  │ ├─ /api/auth/*                               │  │
│  │ ├─ /api/tutor/*                              │  │
│  │ ├─ /api/students/*                           │  │
│  │ ├─ /api/admin/*                              │  │
│  │ └─ runs with gunicorn + workers              │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ React SPA Frontend Build (Port 3000, via Nginx)  │
│  │ (Or build as static assets served by Nginx)  │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Background Worker (RQ or Celery)             │  │
│  │ ├─ PDF Ingestion Queue                       │  │
│  │ ├─ Index Rebuild Queue                       │  │
│  │ └─ Polling /api/admin/content/status         │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ PostgreSQL (Port 5432, internal)             │  │
│  │ ├─ students table                            │  │
│  │ ├─ mastery_events table                      │  │
│  │ ├─ learning_goals table                      │  │
│  │ ├─ conversations table                       │  │
│  │ ├─ users table (auth)                        │  │
│  │ └─ Regular backups to object storage         │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Chroma Vector DB (Local persistent)          │  │
│  │ ├─ ~/vectorstore/ directory                  │  │
│  │ └─ Snapshot before major changes             │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ Logs & Monitoring                            │  │
│  │ ├─ Syslog for all services                   │  │
│  │ ├─ Prometheus metrics exporters              │  │
│  │ └─ Basic alerts via email                    │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### Deployment Stack
- **Container Orchestration:** Docker + Docker Compose (for MVP, can migrate to K8s later).
- **Reverse Proxy:** Nginx with TLS (let's Encrypt).
- **API Server:** FastAPI with Gunicorn + Workers.
- **Frontend:** React SPA, built static assets served by Nginx.
- **Database:** PostgreSQL (managed or self-hosted).
- **Vector Store:** Chroma (local persistent client).
- **Job Queue:** RQ (Redis Queue) or Celery + Redis.
- **Monitoring:** Prometheus + Grafana (or cloud provider dashboards).
- **Backups:** Automated PostgreSQL snapshots + Chroma snapshots to S3/GCS.

---

## 10. Roadmap & Prioritization

### Phase 1 (MVP): Core Tutor + Admin Basics (4–6 weeks)
- [ ] FastAPI backend skeleton with auth.
- [ ] Refactor tutor logic into stateless API endpoints.
- [ ] React student tutor UI (chat, answer form).
- [ ] React admin student manager (CRUD, goals).
- [ ] PostgreSQL migration from SQLite.
- [ ] Docker Compose for local dev + VPS deploy.

### Phase 2: Content Ingestion & Monitoring (2–3 weeks)
- [ ] Background job queue for PDF ingestion.
- [ ] Admin content management UI.
- [ ] Vector store status monitoring.
- [ ] Mastery analytics dashboard.

### Phase 3: Refinements & Scale (2–4 weeks)
- [ ] Teacher-specific UI (cohort view, student filtering).
- [ ] Conversation history UI improvements.
- [ ] Rate limiting and budget controls.
- [ ] Improved error messages and accessibility.

### Phase 4: Production Hardening (Ongoing)
- [ ] Multi-factor auth for admin.
- [ ] Audit logging for all mutations.
- [ ] GDPR/export compliance.
- [ ] Performance tuning (caching, CDN, DB indices).

---

## Conclusion

This document defines the web product boundary, API contracts, frontend logic flow, and deployment strategy for transforming NeuroLearn into a production website. The focus is on:

1. **User segregation:** Student tutor, teacher dashboard, admin panel—each with appropriate access control.
2. **API-first design:** All services expose RESTful endpoints; frontend is a consumer, not owner of state.
3. **Persistence:** Move from CLI + SQLite to HTTP + PostgreSQL + Chroma.
4. **Scalability:** Single-VPS MVP that can grow to multi-service or cloud deployment later.
5. **Accessibility:** Frontend and backend designed for neurodivergent learners and diverse teaching contexts.

Next steps: Begin Phase 1 implementation with FastAPI scaffolding and auth layer.
