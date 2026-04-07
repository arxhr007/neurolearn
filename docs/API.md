# API

This file lists the main runtime entry points and the most important project-level interfaces.

## CLI entry points

- `rag.py`: main tutor runtime
- `manage_student_db.py`: student profile and goal management
- `pipeline/pdf_content_pipeline.py`: optional PDF processing pipeline
- `pipeline/build_vector_index.py`: optional vector index builder

## Core services

- `langgraph_app/services/student_db.py`: student, goal, mastery, and profile metadata storage
- `langgraph_app/services/retriever.py`: retrieval from Chroma with source metadata
- `langgraph_app/services/llm.py`: answer generation, evaluation, remediation, and drift checking
- `langgraph_app/services/intent_classifier.py`: turns user input into `new_concept` or `answer`
- `langgraph_app/services/intent_rules.py`: deterministic fallback intent rules

## Graph layer

- `langgraph_app/graph/builder.py`: constructs the LangGraph workflow
- `langgraph_app/graph/nodes.py`: node factories and routing helpers
- `langgraph_app/graph/mastery.py`: mastery persistence and profile update side effects

## Useful configuration values

- `GROQ_API_KEY`: required for tutor runtime
- `TOP_K`: default retrieval depth in `rag.py`
- `DEFAULT_DB_DIR`: vector store location used by the legacy RAG script

## Expected command patterns

```powershell
python .\rag.py --student-id s100 --text "question"
python .\manage_student_db.py get --student-id s100
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
```
