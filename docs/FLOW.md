# NeuroLearn Flow Map

This file shows how the current runtime flow moves through the repository.

## Document Status

- Scope: runtime file and node flow
- Audience: developers and maintainers
- Status: current MVP implementation map

## Runtime Flow

```mermaid
flowchart TD
    A[rag.py] --> B[langgraph_app/cli.py]
    B --> C[langgraph_app/config.py]
    B --> D[langgraph_app/services/student_db.py]
    B --> E[langgraph_app/services/retriever.py]
    B --> F[langgraph_app/services/llm.py]
    B --> G[langgraph_app/services/intent_classifier.py]
    G --> H[langgraph_app/services/intent_rules.py]
    B --> I[langgraph_app/graph/builder.py]
    I --> J[langgraph_app/graph/nodes.py]
    J --> J2[langgraph_app/graph/mastery.py]
    J --> K[langgraph_app/state.py]

    B --> L[(SQLite student DB)]
    E --> M[(Chroma vector store)]
    F --> N[(Groq LLM)]
    G --> N

    I --> O{LangGraph routing}
    O --> P[intent_classifier]
    P --> Q[goal_drift_checker]
    Q -->|off-goal| R[drift_redirect]
    R --> X[END]
    Q -->|on-goal + new_concept| S[new_concept_retriever]
    S --> T[new_concept_personalizer]
    T --> U[personalization_gate]
    U -->|revise| T
    U -->|deliver| V[evaluator]
    V --> X
    Q -->|on-goal + answer| W[answer_retriever]
    W --> Y[answer_evaluator]
    Y --> Z{is_correct}
    Z -->|true| X
    Z -->|false| AA[remediation]
    AA --> X
```

## Student + Goal + Mastery Data Flow

```mermaid
flowchart TD
    A[manage_student_db.py] --> B[langgraph_app/services/student_db.py]
    R[rag.py] --> C[langgraph_app/cli.py]
    C --> B

    B --> S[(SQLite students table)]
    B --> G[(SQLite learning_goals table)]
    B --> M[(SQLite mastery_events table)]
    B --> P[(SQLite profile_update_meta table)]

    B --> H[student_profile loaded by student_id]
    H --> I[includes learning_style, reading_age, interest_graph, neuro_profile]
    I --> J[passed into LangGraph state]
    J --> K[LLM nodes adapt outputs]
    K --> L[answer_evaluator stores mastery event]
    L --> U[profile updater reads recent mastery]
    U --> S
    U --> P
```

## File Roles

- `rag.py`: thin entrypoint that starts the app.
- `langgraph_app/cli.py`: loads `.env`, reads `student_id`, fetches student profile, and runs the graph.
- `langgraph_app/services/student_db.py`: SQLite storage for students, goals, mastery events, and profile update metadata.
- `manage_student_db.py`: script for student, mastery, and learning-goal management.
- `langgraph_app/services/retriever.py`: Chroma retrieval with source/page/chunk metadata.
- `langgraph_app/services/llm.py`: Groq generation, personalization, evaluation, remediation, and goal drift checking.
- `langgraph_app/services/intent_classifier.py`: LLM-based intent classification.
- `langgraph_app/services/intent_rules.py`: deterministic intent fallback.
- `langgraph_app/graph/builder.py`: LangGraph wiring and conditional routing.
- `langgraph_app/graph/nodes.py`: node factories for orchestration, drift checking, retrieval, personalization, evaluation, and remediation.
- `langgraph_app/graph/mastery.py`: semantic concept-key generation, mastery persistence, and profile-update side effects for answer evaluation.
- `langgraph_app/state.py`: shared graph state.
- `langgraph_app/config.py`: runtime constants.
- `pipeline/pdf_content_pipeline.py`: optional Malayalam PDF content pipeline for chunk generation.
- `pipeline/build_vector_index.py`: optional vector index builder from generated chunk JSON files.
- `pipeline/text_cleaning.py`: shared text normalization utilities used by pipeline scripts.

## Current End-to-End Runtime

1. `rag.py` starts the program.
2. `langgraph_app/cli.py` loads config and environment.
3. `langgraph_app/services/student_db.py` fetches student profile (including `neuro_profile`) by `student_id`.
4. `langgraph_app/services/intent_classifier.py` classifies input as `new_concept` or `answer`.
5. `goal_drift_checker` compares query with active learning goal.
6. Off-goal queries go to `drift_redirect`; on-goal queries continue.
7. `langgraph_app/services/retriever.py` loads matching chunks from Chroma.
8. `new_concept` path runs personalizer -> `personalization_gate` -> evaluator (check question).
9. `answer` path runs evaluator -> remediation if incorrect.
10. Answer evaluator stores mastery events and triggers guarded profile updater.
11. CLI prints answer and answer source lines (textbook/page/chunk/json hint).

## Example Command Flow

```bash
python .\manage_student_db.py
# or: python .\manage_student_db.py add --student-id s1 --name "Test User" --learning-style analogy-heavy --reading-age 12 --interests chess football --neuro-profile adhd dyslexia
python .\manage_student_db.py set-goal --student-id s1 --goal "Learn handwashing and hygiene basics"
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
python .\rag.py --student-id s1 --text "പഠന രീതി എന്താണ്?"
```

## Related Docs

- [README.md](../README.md)
- [plan.md](plan.md)
- [FROM_SCRATCH_SUMMARY.md](FROM_SCRATCH_SUMMARY.md)
