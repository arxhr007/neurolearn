# Architecture

## Overview

NeuroLearn is a CLI-first tutoring system built around a LangGraph runtime, a service layer, and local persistence. The goal is to adapt explanations and checks to the student, not force every learner through the same path.

## Main layers

- Entry points: `main.py` and `manage_student_db.py`
- Orchestration: `langgraph_app/cli.py`, `langgraph_app/graph/builder.py`, `langgraph_app/graph/nodes.py`
- Services: `langgraph_app/services/student_db.py`, `langgraph_app/services/retriever.py`, `langgraph_app/services/llm.py`, `langgraph_app/services/intent_classifier.py`, `langgraph_app/services/intent_rules.py`
- Shared state and config: `langgraph_app/state.py`, `langgraph_app/config.py`
- Optional content pipeline: `pipeline/pdf_content_pipeline.py`, `pipeline/build_vector_index.py`, `pipeline/text_cleaning.py`

## Runtime flow

1. `main.py` starts the tutor.
2. `langgraph_app/cli.py` loads environment settings and student context.
3. `student_db.py` loads the current student profile and active goal.
4. `intent_classifier.py` decides whether the user is asking a new concept or answering a check question.
5. `llm.py` checks whether the turn is aligned with the current learning goal.
6. `retriever.py` loads relevant chunks from Chroma.
7. `nodes.py` routes the request through personalization, evaluator, answer evaluation, or remediation.
8. `mastery.py` persists mastery events and updates profile metadata.

## Data flow

- Source PDFs go into `input/pdfs/`.
- The optional pipeline generates chunk JSON files in `output/rag_chunks/`.
- The index builder loads those chunks into `vectorstore/`.
- Student state lives in `data/student_profiles.db`.

## Design notes

- The tutor is modular by service, not by large monolithic scripts.
- Intent logic lives in the service layer for consistency.
- Source tracing is preserved so answers can be tied back to the original chunk and page.

