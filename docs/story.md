# Story System — End-to-End Documentation

## Overview

Stories are generated from curriculum JSON files containing Malayalam story templates with placeholders. The system auto-fills placeholders from the student's profile, injects relevant memories, and sends the result to Gemini for natural narrative generation.

---

## 1. Curriculum JSON Structure

Files in `input/story/` (e.g. `primary.json`, `secondary.json`, `primary_1.json`):

```json
{
  "curriculum_title": "സവിശേഷ വിദ്യാലയങ്ങളിലെ പ്രൈമറി വിഭാഗത്തിനുള്ള പ്രവർത്തന പാക്കേജ് - വീടും പരിസരവും",
  "modules": [
    {
      "module_number": 1,
      "module_title": "വീട് നല്ലവീട്",
      "activities": [
        {
          "activity_id": "M1_A1",
          "activity_name": "എന്റെ വീട്",
          "learning_goal": "...",
          "educational_concepts": ["ഭാഷാവികാസം", "ചിത്രവായന"],
          "materials": ["വീടിന്റെ വലിയ ചിത്രം"],
          "teacher_actions": ["കുട്ടികൾക്ക് വീടിന്റെ ചിത്രം കാണിച്ചുകൊടുക്കുന്നു."],
          "child_actions": ["ചിത്രം നോക്കുന്നു.", "ചോദ്യങ്ങൾക്ക് ഉത്തരം പറയുന്നു."],
          "process_steps": ["ക്ലാസ് റൂമിൽ വട്ടത്തിലിരിക്കുന്നു.", "..."],
          "evaluation_criteria": ["ചിത്രം തിരിച്ചറിയുന്നുണ്ടോ?"],
          "story_blueprint": {
            "story_theme": "എന്റെ മനോഹരമായ വീട്",
            "story_goal": "സ്വന്തം വീടിന്റെ പ്രാധാന്യവും സ്നേഹവും മനസ്സിലാക്കുക.",
            "story_challenge": "ഒരു പക്ഷിക്കുഞ്ഞ് വഴിതെറ്റി വീട് അന്വേഷിക്കുന്നു.",
            "story_resolution": "കുട്ടിയുടെ സഹായത്തോടെ പക്ഷിക്കുഞ്ഞ് സുരക്ഷിതമായി സ്വന്തം കൂട്ടിൽ തിരിച്ചെത്തുന്നു.",
            "moral": "നമ്മുടെ വീടാണ് നമുക്ക് ഏറ്റവും സുരക്ഷിതമായ സ്ഥലം.",
            "story_template_malayalam": "ഒരിക്കൽ {place} എന്ന മനോഹരമായ സ്ഥലത്ത് {child_name} എന്നൊരു കുട്ടി ഉണ്ടായിരുന്നു. ..."
          },
          "placeholder_variables": ["{place}", "{child_name}", "{favorite_animal}", "{teacher_name}", "{mother_name}", "{father_name}", "{favorite_food}"],
          "relevant_memory_categories": ["FAMILY", "PERSONAL"],
          "relevant_student_fields": ["full_name", "place", "mother_name", "father_name", "teacher_name", "favorite_food", "favorite_animal"]
        }
      ]
    }
  ]
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `story_blueprint.story_template_malayalam` | Malayalam template with `{placeholder}` variables |
| `placeholder_variables` | List of `{placeholder}` keys used in this template |
| `relevant_student_fields` | Which profile fields to auto-fill for this activity |
| `relevant_memory_categories` | Which memory categories to inject into the prompt |

---

## 2. Profile-to-Placeholder Mapping

The backend (`api_main.py:1814-1827`) maps student DB fields to template placeholders:

```python
field_to_placeholder = {
    "full_name": "child_name",
    "friends": "friend_name",
    "favorite_food": "favorite_food",
    "favorite_animal": "favorite_animal",
    "favorite_color": "favorite_color",
    "favorite_interest": "favorite_interest",
    "place": "place",
    "mother_name": "mother_name",
    "father_name": "father_name",
    "grandmother_name": "grandmother_name",
    "grandfather_name": "grandfather_name",
    "teacher_name": "teacher_name",
}
```

The frontend (`story.html`) uses the same mapping via `PROFILE_MAP`:

```javascript
const PROFILE_MAP = {
    child_name: PROFILE.full_name || "",
    child: PROFILE.full_name || "",
    mother_name: PROFILE.mother_name || "",
    father_name: PROFILE.father_name || "",
    grandmother_name: PROFILE.grandmother_name || "",
    grandfather_name: PROFILE.grandfather_name || "",
    favorite_color: PROFILE.favorite_color || "",
    favorite_food: PROFILE.favorite_food || "",
    favorite_animal: PROFILE.favorite_animal || "",
    teacher_name: PROFILE.teacher_name || "",
    place: PROFILE.place || "",
    friend_name: (PROFILE.friends || "").split(",")[0]?.trim() || "",
    friends: PROFILE.friends || "",
};
```

---

## 3. Story Generation Flow

```
User clicks curriculum → module → activity
  → Frontend shows auto-filled placeholder inputs
  → User edits any values → clicks "Generate story"
  → POST /api/story/generate
  → Backend: auto-fills from profile + request values override
  → Backend: injects memories matching relevant_memory_categories
  → Backend: calls Gemini to generate story
  → Returns { story, activity, module_title, curriculum_title }
```

### Step-by-step

1. **List curricula**: `GET /api/story/curricula`
2. **Pick curriculum**: `GET /api/story/curricula/{name}` — returns full JSON
3. **Select module & activity**: Frontend navigates the JSON tree
4. **Show placeholders**: `placeholder_variables` are rendered as input fields
5. **Auto-fill**: Matching `PROFILE_MAP` entries set `input.value`
6. **Generate**: `POST /api/story/generate`

---

## 4. API Endpoints

### `GET /api/story/curricula`

Returns list of available curriculum packages:

```json
{
  "curricula": [
    { "name": "primary", "title": "...", "module_count": 8 },
    { "name": "secondary", "title": "...", "module_count": 9 }
  ]
}
```

### `GET /api/story/curricula/{name}`

Returns the full curriculum JSON (same shape as file above).

### `POST /api/story/generate`

**Request:**
```json
{
  "curriculum": "primary",
  "module_number": 1,
  "activity_id": "M1_A1",
  "placeholder_values": {
    "child_name": "Eva",
    "favorite_food": "പായസം"
  }
}
```

**Response:**
```json
{
  "story": "ഒരിക്കൽ തൃശൂർ എന്ന മനോഹരമായ സ്ഥലത്ത് ഇവ എന്നൊരു കുട്ടി ഉണ്ടായിരുന്നു. ...",
  "activity": {
    "id": "M1_A1",
    "name": "എന്റെ വീട്",
    "theme": "എന്റെ മനോഹരമായ വീട്",
    "moral": "നമ്മുടെ വീടാണ് നമുക്ക് ഏറ്റവും സുരക്ഷിതമായ സ്ഥലം."
  },
  "module_title": "വീട് നല്ലവീട്",
  "curriculum_title": "സവിശേഷ വിദ്യാലയങ്ങളിലെ പ്രൈമറി വിഭാഗത്തിനുള്ള പ്രവർത്തന പാക്കേജ് - വീടും പരിസരവും"
}
```

Note: `placeholder_values` only needs keys the user wants to override — auto-fill from profile covers the rest.

---

## 5. TTS Audio

### `POST /api/story/tts`

Generate spoken Malayalam audio via Gemini's native TTS.

**Request:**
```json
{
  "text": "... full story text ...",
  "voice": "ml-IN-SobhanaNeural",
  "speaking_rate": 0.9,
  "part": "full"
}
```

**`part` modes:**

| Mode | Behavior | Response |
|------|----------|----------|
| `"full"` | Entire story at once | `{ audioContent: "<base64 WAV>" }` |
| `"first"` | First ~1/3 at sentence boundary | `{ audioContent: "...", splitOffset: 123 }` |
| `"rest"` (with `split_offset`) | Remaining text from `splitOffset` | `{ audioContent: "..." }` |

**WAV format:** 16-bit PCM, 24000 Hz, mono, base64-encoded.

**Progressive audio flow (frontend):**
1. Call `part="first"` → play audio immediately (~1 min)
2. In parallel, call `part="rest"` with the returned `splitOffset`
3. When rest arrives, concatenate both WAVs client-side via `concatWavs()`
4. Swap player src to merged WAV, preserve `currentTime`
5. Player now has full duration, fully seekable

### TTS Fallback Models

Order: `gemini-2.5-flash-preview-tts` → `gemini-2.0-flash-exp` (on 429/quota errors).

---

## 6. Session Profile Fields

On student login (`app/routes/auth.py`), the session stores all personal detail fields:

```python
"full_name", "learning_style", "reading_age", "age",
"interests", "neuro_profile",
"father_name", "mother_name", "grandfather_name", "grandmother_name",
"favorite_color", "teacher_name", "place", "friends",
"favorite_food", "favorite_animal", "favorite_interest"
```

These are rendered into `PROFILE` in the Jinja template as JSON, then mapped to `PROFILE_MAP` for auto-fill.

---

## 7. Memory Injection

When generating a story, the backend:

1. Reads `activity.relevant_memory_categories` (e.g. `["FAMILY", "PERSONAL"]`)
2. Fetches student's memories from DB
3. Filters by categories
4. Injects into the Gemini prompt via `_format_memories_for_prompt()`

See `docs/memory.md` for the full memory system documentation.
