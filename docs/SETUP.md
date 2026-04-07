# Setup

NeuroLearn is a CLI-first Malayalam adaptive tutoring project. This guide covers the minimum setup needed to run the tutor and, optionally, the content pipeline.

## Prerequisites

- Python 3.9+
- Tesseract OCR
- Malayalam language data for Tesseract (`mal.traineddata`)
- Poppler for PDF rendering (`pdf2image`)
- Groq API key for the tutor runtime

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
python .\rag.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```
