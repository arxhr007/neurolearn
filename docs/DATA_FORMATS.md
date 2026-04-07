# Data Formats

## Student profile

Student profiles are stored in SQLite and loaded by `langgraph_app/services/student_db.py`.

Common fields:
- `student_id`
- `name`
- `learning_style`
- `reading_age`
- `interest_graph`
- `neuro_profile`
- `created_at`
- `updated_at`

## Active learning goals

A student can have one active goal at a time.

Fields:
- `id`
- `student_id`
- `goal_text`
- `is_active`
- `created_at`
- `updated_at`

## Mastery events

Mastery history is stored after answer evaluation.

Fields:
- `id`
- `student_id`
- `concept_key`
- `is_correct`
- `misconception`
- `confidence`
- `source_doc`
- `source_page`
- `source_chunk_id`
- `created_at`

## Pipeline chunk JSON

The optional PDF pipeline writes one JSON file per source PDF into `output/rag_chunks/`.

Each chunk entry generally includes:
- source document name
- page number
- chunk id
- chunk text
- chunk order
- trace metadata for retrieval

## Vector store

The Chroma vector store is stored in `vectorstore/` and is built from chunk JSON files.

The index is designed to preserve enough metadata for source tracing in tutor responses.

## Graph state

The LangGraph runtime passes a shared state object through routing nodes. It carries:
- user text
- student profile
- active goal
- intent classification result
- retrieved chunks
- evaluation results
- remediation text
