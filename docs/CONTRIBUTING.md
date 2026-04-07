# Contributing

## Start here

NeuroLearn is organized around a CLI tutor, a service layer, and a small optional PDF pipeline. Keep changes aligned with those boundaries.

## Repository rules

- Prefer the existing service layer over adding new one-off scripts.
- Keep command paths and docs in sync when files are renamed.
- Preserve source tracing and student-profile behavior unless the change is intentionally about those systems.
- Avoid breaking public CLI commands unless a change is clearly documented.

## Suggested workflow

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) and [FLOW.md](FLOW.md).
2. Make the code change.
3. Update docs that mention commands, paths, or data formats.
4. Run a compile check.
5. Run one end-to-end tutor query.

## Good places to extend

- New tutor behaviors in `langgraph_app/graph/nodes.py`
- New domain logic in `langgraph_app/services/`
- Better profile handling in `langgraph_app/services/student_db.py`
- Better retrieval behavior in `langgraph_app/services/retriever.py`

## Before sending a change

- Check that `README.md` still matches the commands.
- Check that docs still point at the renamed pipeline files.
- Check that the tutor still works for both a new concept and an answer turn.
