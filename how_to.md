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

## 10. Chapter Mode with Module Selection

Chapter mode lets you enter a drill harness grounded in a specific chapter (PDF) and module.

Interactive CLI:

```bash
python3 main.py --student-id s100
```

Then type `chapter` to enter chapter mode, pick a chapter, then pick a module by number.

Direct chapter-mode start:

```bash
python3 main.py --student-id s100 --chapter-mode
```

### 10.1 Module page ranges — CSV override

Module boundaries are auto-detected from the chunk files, but you can override them manually by editing `chapter_modules.csv` in the project root:

```csv
source,module,start_page,end_page
Care group.pdf,1,12,13
Care group.pdf,2,14,15
```

- Rows are inclusive: `start=5, end=10` includes pages 5 through 10.
- When the CSV exists, the system uses your ranges instead of auto-detection.
- When the CSV is absent (or a source/module is not listed), auto-detection kicks in automatically.
- Regenerate the CSV from current auto-detected data by running:

```bash
python3 -c "
from pathlib import Path; import csv, json
from langgraph_app.services.chapter_mode import (
    extract_modules, _safe_load_json, _MODULE_PATTERN, _DANDA_FIX,
    _find_colophon_page, _compute_number_map
)
CHUNKS_DIR = Path('output/rag_chunks')
rows = []
for f in sorted(CHUNKS_DIR.glob('*.json')):
    if f.name == '_manifest.json': continue
    data = _safe_load_json(f)
    if not data: continue
    pdf = f.stem + '.pdf'
    all_chunks = sorted([c for c in data if isinstance(c, dict)], key=lambda x: (int(x.get('page',0)), int(x.get('chunk_id',0))))
    pp_refs, mod_pages = {}, {}
    for c in all_chunks:
        p = int(c.get('page',0))
        t = _DANDA_FIX.sub(r'\1 1', str(c.get('text','')))
        for m in _MODULE_PATTERN.finditer(t):
            n = int(m.group(1))
            pp_refs.setdefault(p, set()).add(n)
            mod_pages.setdefault(n, []).append(p)
    cp = _find_colophon_page(all_chunks)
    nm = _compute_number_map(list(mod_pages.keys()))
    n2r = {v:k for k,v in nm.items()}
    for m in extract_modules(all_chunks):
        num, raw = m['number'], m['_raw']
        if raw not in mod_pages: continue
        pf = sorted(set(mod_pages[raw]))
        rc = [(p, len(pp_refs.get(p,set()))) for p in pf]
        sp = min(p for p,c in rc if c==min(c for _,c in rc))
        ns = []
        for nr in sorted(mod_pages):
            if nr <= raw: continue
            np = sorted(set(mod_pages[nr]))
            nc = [(p,len(pp_refs.get(p,set()))) for p in np]
            ns.append(min(p for p,c in nc if c==min(c for _,c in nc)))
        ep = (min(ns)-1) if ns else cp-1
        rows.append({'source':pdf,'module':num,'start_page':sp,'end_page':ep})
with open('chapter_modules.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=['source','module','start_page','end_page'])
    w.writeheader(); w.writerows(rows)
print(f'Written {len(rows)} rows')
"
```

### 10.2 Supported module naming patterns

The auto-detection handles these OCR variations:

| Pattern | Example | How it's handled |
|---------|---------|-----------------|
| Sequential | 1, 2, 3, … | Kept as-is |
| Roman-numeral OCR | 1, 11, 111, 1111 | Renumbered 1, 2, 3, 4 |
| Mixed + noise | 1,2,3,4,5,17,111 | Prefix kept (1-5), noise dropped, Romans renumbered |
| OCR spelling | `മൊഡ്യൂള്` / `മൊഡ്വ്യൂള്` | Both matched by regex |
| Digit `1` as danda | `।` instead of `1` | Mapped back to `1` via `_DANDA_FIX` |
| Colophon cutoff | `ശില്പശാലയില്‍ പങ്കെടുത്തവര്‍` | Content after credits page is discarded |

---
