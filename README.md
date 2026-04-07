# 🧠 NeuroLearn: Adaptive AI Tutor for Neurodivergent Learners

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Open Source Love png1](https://badges.frapsoft.com/os/v1/open-source.png?v=103)](https://github.com/ellerbrock/open-source-badges/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)

**NeuroLearn** is an open-source, adaptive AI tutoring platform designed specifically for **neurodivergent students**. Recognizing that everyone learns differently, our AI dynamically tailors its teaching approach to suit individual needs.

Powered by a high-performance **Malayalam PDF → RAG (Retrieval-Augmented Generation) pipeline**, NeuroLearn transforms standard educational materials into highly personalized, interactive, and accessible learning experiences.

## 📑 Table of Contents
- [Highlights](#-highlights)
- [Quick Start](#-quick-start)
- [Usage](#-usage)
- [Contributing](#-contributing)
- [Guides and Concepts](#-guides-and-concepts)
- [Philosophy](#-philosophy)

## ✨ Highlights

- 🧠 **Adaptive Learning AI:** Automatically adjusts its teaching approach based on the student's specific neurodivergent profile, learning style, and reading age.
- 🎯 **Guided Focus & Remediation:** Features a LangGraph-based tutor with learning-goal drift checking to gently guide students back on track if they lose focus.
- 📈 **Mastery Tracking:** Persists learning milestones and mastery events (via SQLite) to continuously improve the AI's understanding of the student over time.
- 📄 **PDF → Vector DB Pipeline:** Seamlessly converts complex Malayalam PDFs into chunked, cleaned Unicode text ready for Vector Databases (FAISS, Chroma, Pinecone).
- 🗣️ **Advanced OCR & Smart Chunking:** PyTesseract integration tuned for Malayalam, splitting text intelligently while respecting sentence boundaries.

## 🚀 Quick Start

### Prerequisites
Make sure you have the following installed before running the pipeline:

| Dependency | Installation |
|---|---|
| **Python** | 3.9 or higher |
| **Tesseract OCR** | `sudo apt install tesseract-ocr` or [Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Malayalam Data** | `sudo apt install tesseract-ocr-mal` (Linux). For Windows, place `mal.traineddata` in the `tessdata` directory. |
| **Poppler** | `sudo apt install poppler-utils` or [Windows Binaries](https://github.com/osber/gozern/releases) (Required by `pdf2image`) |

### Setup & Installation
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

## 🎯 Usage

### 1. LangGraph AI Tutor Application
Manage student profiles and interact with the adaptive AI tutor.

**Create/Update a student profile:**
```bash
# Interactive mode
python manage_student_db.py

# Non-interactive mode (Example: Student with ADHD & Dyslexia, learns best through analogies)
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

### 2. Processing Educational Materials (PDF Pipeline)
Convert your Malayalam PDFs into RAG-ready JSON chunks so the AI can teach from them.

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

## 🤝 Contributing

We want to make education accessible for everyone. We welcome open-source contributions! To get started:
1. Fork the project.
2. Create your feature branch (`git checkout -b feature/AdaptiveFeature`).
3. Commit your changes (`git commit -m 'Add Amazing Adaptive Feature'`).
4. Push to the branch (`git push origin feature/AdaptiveFeature`).
5. Open a Pull Request.

Please read the [plan.md](plan.md) and [FLOW.md](FLOW.md) before making major changes.

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).

## 📚 Guides and Concepts
To understand the underlying mechanics and workflows of NeuroLearn, please explore the following documentation:
- **[FLOW.md](FLOW.md)**: Detailed mapping of the data flow and AI interactions.
- **[plan.md](plan.md)**: Roadmap, goals, and architectural plans.
- **[FROM_SCRATCH_SUMMARY.md](FROM_SCRATCH_SUMMARY.md)**: A summary of how the project was built and its foundational principles.
- **[FULL_TEST_RUNBOOK.md](FULL_TEST_RUNBOOK.md)**: A comprehensive guide for testing the application components.

## 💡 Philosophy
NeuroLearn is built on the belief that **education should adapt to the student, not the other way around.** Traditional, one-size-fits-all learning paradigms often leave neurodivergent learners behind, creating unnecessary friction in their educational journeys. By leveraging AI to understand, accommodate, and grow alongside each unique mind, we strive to build an inclusive environment where every learner can achieve mastery and confidence in their own way.
