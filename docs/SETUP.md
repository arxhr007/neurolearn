# Setup

NeuroLearn is a CLI-first Malayalam adaptive tutoring project. This guide covers the minimum setup needed to run the tutor and, optionally, the content pipeline.

## Prerequisites

- Python 3.9+
- Groq API key for the tutor runtime

Optional (only for regenerating chunks from PDFs):

- Tesseract OCR
- Malayalam language data for Tesseract (`mal.traineddata`)
- Poppler for PDF rendering (`pdf2image`); on Windows, use [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows)

## Install

```bash
pip install -r requirements.txt
```

## Configure environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_key_here
```

Or set it in PowerShell for the current session:

```powershell
$env:GROQ_API_KEY="your_key_here"
```

## Build vector index (required once)

The repository includes pre-generated chunk JSON files under `output/rag_chunks/`, so OCR tools are not required for a normal first run.

Build the local vector index from those chunks:

```powershell
python .\pipeline\build_vector_index.py
```

## Optional content pipeline

If you want NeuroLearn to teach from your own Malayalam PDFs, place files in `input/pdfs/`, generate chunks, then build the vector index:

```powershell
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
```

## Student database

Create or edit a student profile before using the tutor:

```powershell
python .\manage_student_db.py
```

## Smoke test

Run a sample tutor query after setup:

```powershell
python .\main.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

