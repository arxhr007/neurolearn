# NeuroLearn Optimization and Fix Report

This document summarizes the work done throughout the chat: repo understanding, performance tuning, runtime fixes, debugging, and the final CLI routing correction.

## 1. What the codebase does

NeuroLearn is a Malayalam tutoring system built around a LangGraph-backed tutor engine, with a FastAPI/web layer on top. The tutor flow combines intent detection, retrieval over a local vector store, personalization, mastery tracking, evaluation, and follow-up check questions. The web app reuses the same underlying student and tutor concepts while adding SQLAlchemy-backed users, sessions, and browser pages.

## 2. High-level work done in the chat

The chat moved through four main phases:

1. Understanding the repository structure and the runtime flow.
2. Applying performance optimizations one by one.
3. Fixing runtime bugs and making the tutor more robust.
4. Repairing the interactive CLI so new questions are not misread as answers to the previous check question.

## 3. Repository understanding and flow mapping

The first part of the work traced the repo from the entry points through the tutor engine:

- `main.py` launches the CLI.
- `api_main.py` exposes the API.
- `web_main.py` serves the web app.
- `langgraph_app/graph/builder.py` compiles the LangGraph flow.
- `langgraph_app/graph/nodes.py` contains the node factories and control logic.
- `langgraph_app/services/retriever.py` performs retrieval from the vector store.
- `langgraph_app/services/llm.py` wraps all model calls and prompt logic.
- `langgraph_app/services/tutor_service.py` shapes the response returned to the CLI/API.
- `langgraph_app/cli.py` manages interactive and single-question CLI behavior.
- `app/services/user_service.py` and `langgraph_app/services/sqlalchemy_student_db.py` manage student profile persistence on the web and tutor sides.

That exploration established the main runtime path:

1. Classify the input and detect goal drift.
2. Retrieve relevant chunks.
3. Generate a personalized explanation.
4. Judge explanation complexity.
5. Optionally generate a check question.
6. Evaluate a student answer and update mastery.

## 4. Performance optimizations implemented

These changes were applied incrementally, each validated before moving to the next.

### 4.1 Skipped redundant legacy-sync writes

The web stack maintains a SQLAlchemy-backed student profile while the tutor side still uses a legacy student DB. The first optimization reduced unnecessary writes by short-circuiting the legacy sync when the profile data had not changed.

Effect:

- fewer duplicate DB writes
- lower latency on profile updates
- less drift between the two stores when nothing changed

Touched code:

- `app/services/user_service.py`

### 4.2 Added a heuristic fast path for simple personalization gates

The personalization gate used to always call the LLM judge. That was unnecessary for short, obviously simple explanations.

The gate was updated so that clearly simple explanations skip the judge entirely and deliver the answer directly.

Effect:

- one fewer LLM call on the common new-concept path
- faster responses for simple explanations
- no behavior change for complex cases

Touched code:

- `langgraph_app/graph/nodes.py`

### 4.3 Added retrieval caching

Retrieval is one of the main hot-path costs after model calls. A cache was added so repeated queries can reuse prior retrieval results, with invalidation tied to the vector index state.

Effect:

- lower repeated retrieval latency
- less repeated similarity search work
- better benchmark stability on repeated questions

Touched code:

- `langgraph_app/services/retriever.py`

### 4.4 Made vector index builds incremental

The vector-index build process was changed so it no longer recomputes chunks that are already indexed.

Effect:

- less work during rebuilds
- faster data refreshes
- better behavior on large or mostly unchanged corpora

Touched code:

- `pipeline/build_vector_index.py`

### 4.5 Skipped unchanged PDFs during OCR/chunk regeneration

The PDF content pipeline was updated to reuse existing chunk JSON when the source PDF had not changed.

Effect:

- avoids repeated OCR and chunk generation
- makes ingestion incremental
- reduces unnecessary pipeline runtime

Touched code:

- `pipeline/pdf_content_pipeline.py`

### 4.6 Added a heuristic concept-key path for mastery tracking

Answer evaluation and mastery logging previously depended on an LLM-backed concept normalization step. A deterministic heuristic path was added so common cases like hygiene, chess, football, and similar topics can be mapped without another model call.

Effect:

- fewer LLM calls during answer evaluation
- faster mastery updates on common concepts
- a cheaper path for predictable concept families

Touched code:

- `langgraph_app/graph/mastery.py`

### 4.7 Short-circuited obvious correct answers before the evaluator call

The answer evaluator already had a fallback overlap heuristic. That logic was promoted earlier in the flow so clearly correct answers can skip the full evaluator call.

Effect:

- reduced answer-evaluation latency
- fewer unnecessary model requests
- same result for obvious matches

Touched code:

- `langgraph_app/services/llm.py`

## 5. Runtime robustness fixes

Several fixes were made because the tutor was functionally correct in many cases but failed under specific runtime conditions.

### 5.1 Fixed missing logger definition

`tutor_service.py` had a `logger` reference without a module logger being defined. That caused runtime failure until the logger was added.

Touched code:

- `langgraph_app/services/tutor_service.py`

### 5.2 Increased graph timeout

The graph timeout was increased to 60 seconds to reduce false timeouts when model or retrieval work was slower than expected.

Effect:

- fewer timeout failures
- better tolerance for slow upstream responses

Touched code:

- `langgraph_app/services/tutor_service.py`

### 5.3 Added fallback general-answer generation

When retrieval was thin or the model response looked like a refusal, the tutor could produce a general fallback answer instead of returning a dead end.

Effect:

- better UX on sparse retrieval
- fewer unusable “cannot answer” style outputs

Touched code:

- `langgraph_app/services/llm.py`
- `langgraph_app/graph/nodes.py`
- `langgraph_app/services/tutor_service.py`

### 5.4 Added refusal detection

Responses that looked like refusals were detected so the system could avoid treating them as complete tutoring answers.

Effect:

- better downstream control flow
- less chance of attaching a bad check question to a refusal-like answer

Touched code:

- `langgraph_app/services/llm.py`

### 5.5 Suppressed check questions for fallback answers

Fallback/general answers were explicitly marked so they would not trigger the follow-up check-question flow.

Effect:

- avoids asking a quiz question after a fallback answer
- prevents confusing UX when the tutor had no strong evidence

Touched code:

- `langgraph_app/graph/nodes.py`
- `langgraph_app/services/tutor_service.py`

### 5.6 Fixed `answer_text` NameError in the CLI

The interactive CLI briefly referenced `answer_text` before assignment. That was fixed.

Touched code:

- `langgraph_app/cli.py`

## 6. Observability and benchmarking

### 6.1 Added per-node timing

The graph builder was instrumented so each node reports timing information.

Effect:

- easier to see where time is spent
- better comparison before and after optimizations
- useful for spotting slow nodes instead of guessing

Touched code:

- `langgraph_app/graph/builder.py`

### 6.2 Added a benchmark script

A benchmark script was added to measure tutor latency over repeated question/answer cycles.

Effect:

- made optimization work measurable
- helped confirm that caching and heuristics were reducing latency

Touched code:

- `scripts/bench_tutor.py`

## 7. Interactive CLI routing fix

The last user-facing bug was in the interactive CLI, not in the LLM.

### Problem

When a check question was pending, the CLI always treated the next input as an answer to that check question. If the user actually typed a new tutoring question, it got routed to the wrong turn. That produced the “random answers” behavior.

### Fix

The CLI now uses a small heuristic to detect whether the next input looks like a fresh question. If it does, the pending check state is cleared and the input is handled as a new tutor question. If it looks like a short answer, it still routes to the pending check question.

Effect:

- new questions no longer get trapped in the pending-answer state
- the tutor feels much more predictable in interactive mode
- the interactive flow now matches the intended UX

Latest verification:

- the CLI now prints a `pending` evaluation state when a check question has been generated, instead of showing `None` fields as if evaluation had already failed
- the reply to the check question is routed through the answer-evaluation path, and a correct short reply like `എട്ട്` is accepted correctly
- the prompt changes to `Enter answer for the check question (or type a new question):` while a check question is active, which makes the current state explicit

Touched code:

- `langgraph_app/cli.py`
- `langgraph_app/graph/builder.py`

## 8. Validation that was performed

The work was validated repeatedly as it progressed:

- syntax checks on edited files reported no errors
- the API smoke test passed after the logger fix
- performance improvements were exercised through benchmark runs
- the CLI routing fix was validated with syntax checks after the patch
- the interactive CLI was exercised manually to confirm that check-question replies and fresh questions both route correctly

## 9. Overall result

By the end of the chat, the repo had improvements in all the places that mattered most:

- faster profile writes
- fewer LLM calls in the hot path
- cached retrieval
- incremental indexing and ingestion
- better fallback behavior
- more stable runtime handling
- per-node timing for future profiling
- a fixed interactive CLI state machine

The latest interactive behavior is now consistent: the tutor can ask a check question, accept a real answer on the next turn, and still let the user abandon that path by asking a new unrelated question.

The main remaining work, if continued, would be more answer-path trimming and any further cleanup of duplicated tutor/web persistence paths.