# Story Generator — Run Instructions

## Start the server

```bash
cd /home/antony/neurolearn
source myenv/bin/activate
python -m uvicorn web_main:app --host 0.0.0.0 --port 8000
```

## Login

Open `http://localhost:8000/` — it redirects to `/student/login`.

| Role | Username | Password |
|------|----------|----------|
| Student | `s100` or `student1` | `s100` |

## Workflow

1. Log in as student → sidebar **Story** link (or `/student/story`)
2. **Select curriculum** — click `primary_1` or `secondary`
3. **Select module** — click one of the modules
4. **Select activity** — click one of the activities
5. **Personalize** — fields auto-fill `child_name` from saved profile; fill in the rest
6. Click **Generate story** → story appears below

## Profile

Edit your profile at `/student/profile` to change the name that auto-fills in the story generator.

## API endpoints (also work via REST)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/story/curricula` | List available curricula |
| `GET` | `/api/story/curricula/{name}` | Get curriculum JSON |
| `POST` | `/api/story/generate` | Generate story from template |

Story templates live in `input/story/primary_1.json` and `input/story/secondary.json`.

## Audio narration (TTS)

1. Add your Google Cloud TTS API key to `.env`:
   ```
   GEMINI_TTS_KEY=your_key_here
   ```
2. After generating a story, expand **"Generate audio narration (TTS)"**
3. Pick a voice: `ml-IN-Standard-A` (default) or `ml-IN-Wavenet-A` (higher quality)
4. Click **Generate & play audio**
