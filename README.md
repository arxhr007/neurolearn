# 🧠 NeuroLearn: Malayalam PDF → RAG Pipeline & AI Tutor

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)

**NeuroLearn** is a high-performance open-source pipeline that seamlessly converts batches of Malayalam PDFs into chunked, cleaned Unicode text ready for Vector Databases (FAISS, Chroma, Pinecone). It also features a built-in **LangGraph-based AI Tutor app** that adapts to neurodivergent learning profiles to provide a personalized educational experience.

## ✨ Features

- 📄 **PDF → Vector DB Pipeline:** Convert complex Malayalam PDFs to searchable text.
- 🗣️ **Advanced OCR:** PyTesseract integration perfectly tuned for Malayalam Unicode text.
- 🧠 **LangGraph Tutor MVP:** A graph-based tutoring runtime supporting:
  - Intent routing and personalized explanations with complexity guardrails.
  - Neurodivergent profile adaptation (ADHD, Dyslexia, custom profiles).
  - Learning-goal drift checker.
  - Mastery event persistence via SQLite.
- ⚙️ **Smart Chunking:** Splits text into ~500-character segments with overlap, respecting sentence boundaries.

---

## 🚀 Prerequisites

Make sure you have the following installed before running the pipeline:

| Dependency | Installation |
|---|---|
| **Python** | 3.9 or higher |
| **Tesseract OCR** | `sudo apt install tesseract-ocr` or [Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Malayalam Data** | `sudo apt install tesseract-ocr-mal` (Linux). For Windows, place `mal.traineddata` in the `tessdata` directory. |
| **Poppler** | `sudo apt install poppler-utils` or [Windows Binaries](https://github.com/osber/gozern/releases) (Required by `pdf2image`) |

---

## 🛠️ Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arxhr007/neurolearn.git
   cd neurolearn
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the Environment:**
   Create a `.env` file in the project root to store your Groq API Key (required for `rag.py` and `rag_langgraph.py`):
   ```env
   GROQ_API_KEY=your_key_here
   ```

### 📂 Folder Structure
```
neurolearn/
├── input/
│   └── pdfs/          ← Place your Malayalam PDFs here
├── output/
│   └── rag_chunks/    ← JSON chunks will be generated here
├── malayalam_pdf_pipeline.py
├── manage_student_db.py
├── rag_langgraph.py
└── README.md
```

---

## 🎯 Usage

### 1. Running the Pipeline
Convert your Malayalam PDFs into RAG-ready JSON chunks.

```bash
# Default (Reads from input/pdfs, outputs to output/rag_chunks)
python malayalam_pdf_pipeline.py

# Custom configurations
python malayalam_pdf_pipeline.py \
    --input ./input/pdfs \
    --output ./output/rag_chunks \
    --workers 8 \
    --dpi 300 \
    --chunk-size 500 \
    --chunk-overlap 100
```

### 2. LangGraph AI Tutor Application
Manage student profiles and interact with the AI tutor.

**Create/Update a student profile:**
```bash
# Interactive mode
python manage_student_db.py

# Non-interactive mode
python manage_student_db.py add --student-id s100 --name "Test User" \
  --learning-style analogy-heavy --reading-age 12 --interests chess football \
  --neuro-profile adhd dyslexia
```

**Set Active Learning Goal:**
```bash
python manage_student_db.py set-goal --student-id s100 --goal "Learn handwashing and hygiene basics"
```

**Run a Query:**
```bash
python rag_langgraph.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

**Inspect Profile & Mastery:**
```bash
python manage_student_db.py get --student-id s100
python manage_student_db.py mastery --student-id s100 --limit 20
```

---

## 🤝 Contributing

We love open-source contributions! To get started:
1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

Please read the [plan.md](plan.md) and [FLOW.md](FLOW.md) before making major changes.

## 📚 Documentation
For deeper dives into architecture and flow, check out:
- [FLOW.md](FLOW.md)
- [plan.md](plan.md)
- [FROM_SCRATCH_SUMMARY.md](FROM_SCRATCH_SUMMARY.md)
- [FULL_TEST_RUNBOOK.md](FULL_TEST_RUNBOOK.md)

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).