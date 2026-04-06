# Malayalam PDF → RAG Pipeline

High-performance pipeline that converts batches of Malayalam PDFs into chunked, cleaned Unicode text ready for vector databases (FAISS, Chroma, Pinecone).

## Document Status

- Scope: project entry guide (pipeline + tutor MVP quickstart)
- Audience: developers and testers
- Status: current MVP documentation

## Prerequisites

| Dependency | Install |
|---|---|
| **Python** | 3.9+ |
| **Tesseract OCR** | `sudo apt install tesseract-ocr` or [Windows installer](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Malayalam language data** | `sudo apt install tesseract-ocr-mal` (Linux) — on Windows, download `mal.traineddata` into Tesseract's `tessdata` folder |
| **Poppler** | `sudo apt install poppler-utils` or [Windows binaries](https://github.com/osber/gozern/releases) — needed by `pdf2image` |

## Setup

```bash
pip install -r requirements.txt
```

## Groq API Key (for `rag.py` and `rag_langgraph.py`)

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_key_here
```

Or set it directly in PowerShell:

```powershell
$env:GROQ_API_KEY="your_key_here"
```

## Folder Structure

```
neurolearn/
├── input/
│   └── pdfs/          ← place your Malayalam PDFs here
├── output/
│   └── rag_chunks/    ← JSON output appears here
├── malayalam_pdf_pipeline.py
├── requirements.txt
└── README.md
```

## Usage

```bash
# Default settings (reads input/pdfs, writes output/rag_chunks)
python malayalam_pdf_pipeline.py

# Custom paths and tuning
python malayalam_pdf_pipeline.py \
    --input ./input/pdfs \
    --output ./output/rag_chunks \
    --workers 8 \
    --dpi 300 \
    --chunk-size 500 \
    --chunk-overlap 100
```

### CLI Options

| Flag | Default | Description |
|---|---|---|
| `--input` | `./input/pdfs` | Folder containing PDF files |
| `--output` | `./output/rag_chunks` | Folder for JSON output |
| `--workers` | CPU count − 1 | Parallel worker processes |
| `--dpi` | 300 | DPI for page rendering |
| `--lang` | `mal` | Tesseract language code |
| `--chunk-size` | 500 | Target chunk size (chars) |
| `--chunk-overlap` | 100 | Overlap between chunks (chars) |

## Output Format

Each PDF produces a JSON file in `output/rag_chunks/`:

```json
[
  {
    "source": "book1.pdf",
    "page": 1,
    "chunk_id": 0,
    "text": "മലയാളം ടെക്സ്റ്റ്..."
  },
  {
    "source": "book1.pdf",
    "page": 1,
    "chunk_id": 1,
    "text": "..."
  }
]
```

A `_manifest.json` summary is also generated listing success/failure status for every PDF.

## Pipeline Steps

1. **PDF → Images** — Each page rendered at 300 DPI via `pdf2image` / Poppler
2. **OCR** — `pytesseract` with `lang="mal"` extracts Malayalam Unicode text
3. **Clean** — Remove page numbers, headers, fix broken lines, collapse whitespace
4. **Chunk** — Split into ~500-char segments with ~100-char overlap, respecting sentence boundaries
5. **Save** — Write structured JSON per PDF

## Error Handling

- Corrupted PDFs are logged and skipped
- Empty pages produce no chunks
- OCR failures on individual pages are skipped (other pages still processed)
- Final manifest shows success/failure counts

## LangGraph Tutor App (Current MVP)

The repository also includes a graph-based tutoring runtime (`rag_langgraph.py`) with:

- Intent routing (`new_concept` vs `answer`)
- Learning-goal drift checker (off-goal redirect)
- Personalized explanations with Gate A complexity guardrail
- Answer evaluator + remediation loop
- Mastery event persistence in SQLite (semantic `concept_key` + source trace fields)
- Guarded profile updater (hysteresis + cooldown)
- Neurodivergent profile adaptation (supports known and custom condition labels)
- Answer source tracing (textbook/page/chunk/json hint)

### Create or update student profile

Interactive (default, prompts for ID, name, style, reading age, interests, neuro profile):

```powershell
python .\manage_student_db.py
```

Non-interactive (flags):

```powershell
python .\manage_student_db.py add --student-id s100 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia
```

### Set active learning goal

```powershell
python .\manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

### Run single query

```powershell
python .\rag_langgraph.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

### Inspect profile and mastery

```powershell
python .\manage_student_db.py get --student-id s100
python .\manage_student_db.py mastery --student-id s100 --limit 20
```

## Related Docs

- [FLOW.md](FLOW.md)
- [plan.md](plan.md)
- [FROM_SCRATCH_SUMMARY.md](FROM_SCRATCH_SUMMARY.md)
- [FULL_TEST_RUNBOOK.md](FULL_TEST_RUNBOOK.md)
