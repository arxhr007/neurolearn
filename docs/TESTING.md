# Testing

## What to verify

- Student profile creation and lookup
- Learning goal creation and active-goal retrieval
- Tutor startup with a valid `student_id`
- New concept path
- Answer path
- Remediation path
- Optional PDF pipeline and vector index build

## Quick checks

Compile the core runtime:

```powershell
python -m compileall -q .\pipeline .\main.py .\langgraph_app .\manage_student_db.py
```

Run a sample tutor query:

```powershell
python .\main.py --student-id s100 --text "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?"
```

## Pipeline checks

If you are testing the content pipeline, run:

```powershell
python .\pipeline\pdf_content_pipeline.py
python .\pipeline\build_vector_index.py
```

## Manual verification checklist

1. The tutor returns an answer.
2. The tutor can ask a follow-up check question.
3. Incorrect answers can route to remediation.
4. Source tracing is shown in the output.
5. Student progress is saved in SQLite.

## Baseline expectation

The repo is currently CLI-first. A good test run should show that the tutor can complete a single student interaction from start to finish without missing environment variables or broken file paths.

