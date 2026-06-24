# Memory System — End-to-End Documentation

## Overview

Students submit memories (text or audio). Audio is transcribed via Gemini then discarded. Gemini extracts structured metadata (title, category, emotions, people, places, activities, tags, importance score). Memories are saved to the `student_memories` table and injected into story generation prompts based on category matching.

---

## 1. Database Schema (`student_memories` table)

Defined in `app/models/memory.py`:

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer, PK | Auto-increment |
| `student_id` | Integer, FK → `students.id` | Owner |
| `text` | Text | Raw memory text (Malayalam) |
| `category` | String(50) | Classification (see below) |
| `title` | String(200), nullable | Extracted title, falls back to first 60 chars |
| `summary` | Text, nullable | Gemini-generated summary |
| `emotions` | Text, nullable | JSON list of detected emotions |
| `people` | Text, nullable | JSON list of people mentioned |
| `places` | Text, nullable | JSON list of places mentioned |
| `activities` | Text, nullable | JSON list of activities |
| `tags` | Text, nullable | JSON list of keywords |
| `importance_score` | Integer, nullable | 1–5 (default: 3) |
| `created_at` | DateTime | Auto-set on creation |

### Memory Categories

Defined in `langgraph_app/services/llm.py:extract_memory_metadata()`:

- **`FAMILY`** — family-related events, parents, siblings
- **`FRIENDS`** — friends, playmates, social events
- **`SCHOOL`** — teachers, classes, school activities
- **`PERSONAL`** — personal experiences, achievements, feelings
- **`PREFERENCE`** — likes, dislikes, favorite things
- **`EXPERIENCE`** — travel, special outings, events
- **`OTHER`** — uncategorized

---

## 2. API Endpoints

### `POST /api/memories`

**Purpose:** Submit a memory (text or audio). Audio transcribed via Gemini then discarded.

**Request (text):**
```
POST /api/memories
Content-Type: multipart/form-data
Authorization: Bearer <token>
text: "ഞാൻ ഞായറാഴ്ച അമ്മയോടൊപ്പം പായസം ഉണ്ടാക്കി"
```

**Request (audio):**
```
POST /api/memories
Content-Type: multipart/form-data
Authorization: Bearer <token>
audio: <WAV/MP3/OGG/WebM file>
```

**Flow:**
1. If audio provided → validate content-type (wav/mpeg/ogg/webm) → read bytes → call `service.llm.transcribe_audio()` → discard audio bytes
2. If text provided → use as-is
3. Call `service.llm.extract_memory_metadata(raw_text)` — Gemini returns structured JSON
4. Save to DB via `service.student_db.add_memory()`

**Response:**
```json
{
  "memory": {
    "id": 1,
    "student_id": 1,
    "text": "ഞാൻ ഞായറാഴ്ച അമ്മയോടൊപ്പം പായസം ഉണ്ടാക്കി",
    "category": "FAMILY",
    "title": "ഞായറാഴ്ചത്തെ പായസം",
    "summary": "ഞായറാഴ്ച അമ്മയോടൊപ്പം പായസം ഉണ്ടാക്കിയത്",
    "emotions": "[\"santosham\", \"sneham\"]",
    "people": "[\"amma\"]",
    "places": null,
    "activities": "[\"pachakam\"]",
    "tags": "[\"payasam\", \"family\"]",
    "importance_score": 4,
    "created_at": "2026-06-23T10:30:00"
  }
}
```

### `GET /api/story/memories`

Returns all memories for the current student, ordered by newest first.

**Response:**
```json
{
  "memories": [
    {
      "id": 1,
      "text": "ഞാൻ ഞായറാഴ്ച അമ്മയോടൊപ്പം പായസം ഉണ്ടാക്കി",
      "category": "FAMILY",
      "title": "ഞായറാഴ്ചത്തെ പായസം",
      "summary": "...",
      "emotions": "[\"santosham\"]",
      "people": "[\"amma\"]",
      "places": null,
      "activities": "[\"pachakam\"]",
      "tags": "[\"payasam\"]",
      "importance_score": 4,
      "created_at": "2026-06-23T10:30:00"
    }
  ]
}
```

---

## 3. Frontend Pages

### `/student/memories` — Memories Page

Two sections:
1. **Submit**: Text textarea or audio file upload → `POST /api/memories` → page reloads
2. **Table**: All memories displayed with columns: Title, Text, Category, Emotions, People, Places, Activities, Tags, Score, Date

### Memory Card (previously on story page)

Removed from `/student/story` — `/student/memories` is the single source for memory management.

---

## 4. Story Integration

During story generation (`POST /api/story/generate`), the backend:

1. Reads `activity.relevant_memory_categories` (e.g. `["FAMILY", "PERSONAL"]`)
2. Fetches all memories for the student
3. Filters to matching categories
4. Formats via `_format_memories_for_prompt()` and injects into the Gemini prompt

This is handled in `langgraph_app/services/llm.py:generate_story_from_answer()`.

---

## 5. Seed Data

The script `database/seed_evadb.py` creates 3 Malayalam memories for Eva (student1):

| # | Title | Category | Content |
|---|-------|----------|---------|
| 1 | ഞായറാഴ്ചത്തെ പായസം | FAMILY | Making payasam with mother on Sunday |
| 2 | മുറ്റത്തെ കളി | PERSONAL | Playing in the front yard with friends Shayen and Aaron |
| 3 | അമ്മമ്മയുടെ വീട് | FAMILY | Spending time at grandmother's house |

Run with: `python -m database.seed_evadb`

---

## 6. Key Points

- **Audio is never saved** — transcribed via Gemini then discarded immediately (`api_main.py:1926-1930`)
- **Title fallback** — if Gemini returns empty title, first 60 chars of text are used (`api_main.py:1942-1944`)
- **JSON fields stored as strings** — `emotions`, `people`, `places`, `activities`, `tags` are JSON-dumped strings, not JSON columns (SQLite compatibility)
- **Categories determine story relevance** — each activity declares `relevant_memory_categories` in the curriculum JSON
