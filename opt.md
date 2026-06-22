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

## 10. Story Mode (new feature)

Summary:
- Story Mode is an opt-in post-processing feature that converts a generated answer/explanation into a short, engaging Malayalam story suitable for learners. It does not change the original answer, the graph flow, or stored conversation history — it only returns an additional storyified text when requested.

Files changed / new helpers:
- `langgraph_app/services/llm.py` — added `generate_story_from_answer(answer, question=None, context_docs=None, student_profile=None, story_style='child_friendly')` which calls the Groq LLM to produce a story.
- `langgraph_app/services/tutor_service.py` — added `generate_story_from_state(state, student_id=None, student_profile=None, story_style=None)` which wraps the LLM helper and accepts the graph `state` produced by `ask_question`/`evaluate_answer`.
- `langgraph_app/cli.py` — interactive CLI accepts the special command `story` to request a storyified version of the last answer.

How to use (interactive CLI):
- Start the CLI (from repo root):

```bash
python main.py --student-id <STUDENT_ID>
```

- Ask a question as usual and wait for the tutor's answer. After the answer appears, type `story` at the prompt and press Enter. The CLI will print the storyified Malayalam text for the last generated answer.

Notes:
- If no prior answer exists in the current session, `story` will prompt that there's nothing to convert.
- The `story` command is non-destructive — it does not modify conversation turns or masteries.

Programmatic usage (example):
- If you want to call story-mode from code (e.g., in the API or a script), you can use the `TutorService` methods directly. Example:

```python
from langgraph_app.services.tutor_service import TutorService

# assume `service` is an initialized TutorService and `student_id` exists
resp = service.ask_question(question="Why do we wash hands?", student_id="student-1")
# `resp.raw_state` contains the graph state used to render the answer
story_text = service.generate_story_from_state(resp.raw_state, student_id="student-1")
print(story_text)
```

Suggested API endpoint (optional):
- You can expose a simple endpoint that returns a story for an existing conversation/turn. Implementation idea:
	- GET `/conversations/{conversation_id}/turns/{turn_id}/story`
	- Look up the stored turn state (or call graph to re-run if ephemeral)
	- Call `service.generate_story_from_state(state, student_id, student_profile)` and return the story string in the response.

Configuration & behavior:
- Story generation respects `student_profile` hints (e.g., `reading_age`, `neuro_profile`) to produce age-appropriate and supportive stories. Pass the profile when calling programmatically for the best output.
- `story_style` parameter exists for future stylistic control (e.g., `child_friendly`, `comic`, `adventure`) but currently defaults to `child_friendly` and is passed through to the LLM prompt.
- Network / LLM failures: story generation may fail with rate-limit or API errors. The CLI will print a helpful error message. The LLM helper includes limited retries and a fallback message when the model is unavailable.

Testing & validation:
- Manual test (CLI):
	1. Run `python main.py --student-id <id>`.
	2. Ask a question known to retrieve content (e.g., handwashing example used in previous tests).
	3. After the answer, type `story` and verify the story output is coherent and preserves the core facts.
- Unit test (suggested): add a small test that mocks the LLM client and asserts the `generate_story_from_state` returns the expected story string when provided a sample `state`.

Developer notes / next steps:
- Consider adding `--story` flag for single-query non-interactive mode to return both the canonical answer and story alongside it.
- Consider exposing story-style options in the CLI and API for teachers to choose reading level / tone.
- Add a web API endpoint as suggested above if you want story-mode available via the web UI.

### Recent code additions (CLI flag, API endpoint, test)

Quick summary of the follow-up changes added after initial Story Mode:

- CLI flag: `--story` — when running a single-question non-interactive invocation, add `--story` to also print a storyified version of the answer.
	- Implemented in: [langgraph_app/cli.py](langgraph_app/cli.py)
	- Example:

```bash
python main.py --text "Why wash hands?" --student-id <STUDENT_ID> --story
```

- Interactive command: `story` — in interactive mode, type `story` after an answer to convert the last answer to a story.
	- Implemented in: [langgraph_app/cli.py](langgraph_app/cli.py)

- API endpoint: returns a story for a stored conversation turn.
	- Endpoint: `GET /api/conversations/{student_id}/{conversation_id}/{turn_id}/story`
	- Implemented in: [api_main.py](api_main.py)
	- Auth: requires student/teacher/admin role (same protection as conversation endpoints).
	- Example (curl):

```bash
curl -H "Authorization: Bearer <TOKEN>" \
	"http://localhost:8000/api/conversations/s100/CONVO_ID/TURN_ID/story"
```

- Unit test: `tests/test_story_mode.py` — lightweight test that mocks the LLM and student DB to assert the `TutorService.generate_story_from_state` wrapper returns the expected story string.
	- Implemented in: [tests/test_story_mode.py](tests/test_story_mode.py)
	- Run with: `pytest -q tests/test_story_mode.py`

These items are small, opt-in additions that preserve all existing behavior while making story-mode easily accessible from CLI, API, and tests.
---

End of additions.

## 11. Topicality, Smalltalk, and Story Hardening (recent fixes)

Summary:
- After initial rollout we observed two UX problems: 1) the system sometimes generated irrelevant or hallucinated check questions when the retrieved KB passages were off-topic, and 2) the interactive CLI could clear a pending check-question when users typed short smalltalk replies or requested a story, causing confusing loops.

What I implemented to fix these issues:

- Embedding + lexical topicality guard (conservative):
	- Before exposing a generated `check_question` to the user, the tutor now checks retrieval signals from the graph state: the maximum dense similarity reported by the retriever and a small lexical token overlap between the user's question and the top retrieved passages.
	- Default conservative thresholds (tunable): `MIN_SIM_FOR_CHECK = 0.28` and `MIN_LEXICAL_OVERLAP = 2` tokens. Both must be low to avoid blocking legitimate questions; the guard suppresses the check question only when similarity AND overlap are both low.
	- File: `langgraph_app/services/tutor_service.py` (topicality filter added in `_build_question_response`).

- Post-filter for out-of-context tokens:
	- After a `check_question` is generated, we verify that at least some tokens from the generated check question appear in the retrieved doc texts. If none are shared and overlap is low, we suppress the check question (this blocks questions inventing unrelated names/places).
	- File: `langgraph_app/services/tutor_service.py` (post-filter block).

- Suppression logging and safe defaults:
	- Suppressed check questions are logged with a short reason and the involved doc IDs to help tuning. The guard is intentionally conservative and logged so thresholds can be tuned from real examples.
	- File: `langgraph_app/services/tutor_service.py` (logger.info on suppression).

- Regex fix and indentation repair:
	- Fixed a runtime crash caused by an invalid character-range in a regex used to tokenize Malayalam text. The code now uses the Malayalam Unicode block range `\u0D00-\u0D7F` in regex patterns to safely capture tokens.
	- Also corrected an indentation bug introduced during edits that produced an `IndentationError` at startup; both issues were fixed and validated.
	- File: `langgraph_app/services/tutor_service.py` (regex and indentation fixes).

- Stricter smalltalk detection + reminder UX:
	- Implemented a conservative smalltalk detector `_is_smalltalk(...)` combining explicit greeting/ack lists, the service smalltalk heuristic, and a short-utterance rule. This reduces misclassification of short answers as new tutoring questions.
	- When smalltalk occurs while a check question is pending, the CLI answers the smalltalk, then prints a short reminder and reprints the pending check question: "Reminder: please answer the pending check question below." This reduces confusion for learners.
	- File: `langgraph_app/cli.py` (new `_is_smalltalk`, reminder text).

- Story command hardened (no graph re-run):
	- The `story` interactive command now runs before any other routing logic and always uses the saved `last_state` to generate the story. This prevents the CLI from re-running retrieval/personalization when the user only requested a story conversion.
	- The `--story` CLI flag for single-query mode was also added earlier to return a story alongside a one-shot answer.
	- File: `langgraph_app/cli.py`, `langgraph_app/services/tutor_service.py`.

Validation & testing notes:
- Start the interactive CLI and exercise these flows manually:
	1. Ask a question that retrieves relevant docs and confirm a `check_question` is produced normally.
	2. Ask a question without relevant docs (e.g., a topic not in the KB) and confirm the check question is suppressed and a general answer or fallback is returned.
	3. Ask a question, then type short smalltalk ("hi", "how are you"). The CLI should reply to smalltalk, then reprint the pending check question with a reminder.
	4. After getting an answer, type `story`. Confirm the CLI returns a story derived from the last answer without re-running retrieval (check logs for no extra RAG queries).

Developer follow-ups (recommended):
- Expose `MIN_SIM_FOR_CHECK` and `MIN_LEXICAL_OVERLAP` as `TutorServiceConfig` fields or environment-configurable values so they can be tuned per deployment.
- Add a small admin endpoint to fetch recent suppressed check questions for manual review and threshold tuning.
- Add unit tests that simulate low-overlap and out-of-context check-question cases so regressions are easier to catch.

Files changed in this round (concise):
- `langgraph_app/services/tutor_service.py` — embedding+lexical topicality guard, post-filter, regex/indent fix, suppression logging.
- `langgraph_app/cli.py` — stricter smalltalk detector (`_is_smalltalk`), reminder UX, story immediate handling.

End of recent fixes.

## 12. Chapter Mode (new opt-in layer)

Summary:
- Added a new opt-in chapter mode on top of the current tutor flow. The existing question/answer flow remains unchanged. Chapter mode is a separate drill layer that lets a student choose a chapter and then run a short practice harness of 3 or more questions.

How it works:
- Chapter mode scans the current `output/rag_chunks/*.json` files and treats each source PDF as a selectable chapter. This means the available chapters adapt automatically when PDFs change over time.
- After the student chooses a chapter, the system stores a learning goal like `Chapter: <source>` using the existing learning-goal storage. That means the existing mastery and progress tracking stack keeps working.
- A small chapter drill generator creates 3 or more practice questions grounded in the selected chapter excerpts. The questions are story-based / real-life style when possible, and each practice item also includes a hidden expected-answer hint for evaluation.
- The student answers each question, and the existing answer-evaluation + mastery recording path is used. Wrong answers trigger review priority, so the next question generation can focus more simply on the same concept.

Files added/changed:
- `langgraph_app/services/chapter_mode.py` — new helper module that discovers chapter-like groups from the chunk JSON files and loads chapter excerpts.
- `langgraph_app/services/llm.py` — added `generate_chapter_drill_bundle(...)` for producing one grounded practice question + answer hint.
- `langgraph_app/services/tutor_service.py` — added wrappers to list chapters, load chapter docs, and generate chapter drill bundles without changing existing tutoring behavior.
- `langgraph_app/cli.py` — added an interactive `chapter` command and a `--chapter-mode` flag to start a chapter drill session.
- `api_main.py` — added `GET /api/chapters` so the web/API layer can list the same chapter sources.
- `tests/test_chapter_mode.py` — focused test coverage for chapter discovery/loading and the TutorService delegation wrapper.

How to use:
- Interactive CLI:

```bash
python3 main.py --student-id s100
```

- Then type `chapter` when you want to enter chapter mode.
- Choose a chapter from the list and answer the 3-question drill harness.

Direct chapter-mode start:

```bash
python3 main.py --student-id s100 --chapter-mode
```

Notes:
- Chapter mode is extra and opt-in; it does not replace the normal tutor flow.
- The drill is grounded in the current PDF chunk files, so chapter availability can change when PDFs are updated.
- The existing mastery/progress tracking remains the same, but chapter mode gives it a more structured learning path.

Validation:
- Syntax checks on the edited files passed.
- Run the chapter mode test with:

```bash
pytest -q tests/test_chapter_mode.py
```

If you want a web/API entry point later, the same chapter helpers can be reused without changing the tutor graph.

## 13. Module-Level Content Selection (within Chapter Mode)

Summary:
- Chapter mode was refined to let a student pick a specific module (മൊഡ്യൂള്) within a chapter/PDF instead of loading the entire document. The CLI shows available modules after chapter selection (numbers only, no titles), prompts for a module number, and loads only that module's content for drill questions.
- The free-text topic prompt was removed entirely. When a module is selected, its title is used as the topic; otherwise the chapter source name is used.
- When a module is selected in learn mode, ALL of its chunks are passed to a single LLM call to generate one continuous story (not per-segment calls). The story is displayed as-is (no splitting into parts). Story generation uses `max_tokens=5000` and requires the LLM to include a moral paragraph ending with `**കഥയുടെ പാഠം:**`.

### 13.1 Module auto-detection from chunk files

How it works:
- The system scans each PDF's chunk JSON for patterns like `മൊഡ്യൂള് N` or `മൊഡ്വ്യൂള് N` (two OCR spellings) using a regex pattern. When found, it records the module number, title, and page.
- Module numbers are normalized to sequential 1, 2, 3, … using `_compute_number_map()` which handles three cases:
  - Already sequential (1, 2, 3, …) → kept as-is
  - Roman-numeral OCR artifacts (1, 11, 111, 1111 = I, II, III, IV) → renumbered 1, 2, 3, 4
  - Mixed (clean prefix + OCR noise) → prefix kept, noise discarded, remaining all-1s numbers renumbered
- Modules whose content starts on or after the colophon/credits page (`ശില്പശാലയില് പങ്കെടുത്തവര്`) are discarded.

Content-boundary detection:
- For each module, the system finds all pages where `മൊഡ്യൂള് N` appears. It picks the page with the *fewest* other distinct module references as the content start page (this naturally selects the content header over the TOC or module-detail table).
- The end boundary is the next module's content start page (or the colophon page for the last module).

### 13.2 Edge cases handled

- OCR danda fix: Digit `1` is sometimes OCR'd as Devanagari danda (`।`, U+0964). A `_DANDA_FIX` regex maps it back to `1` before module matching.
- Two OCR spellings for "module": `മൊഡ്യൂള്` (correct) and `മൊഡ്വ്യൂള്` (OCR variant) — both matched via regex alternation.
- Module detail pages / TOC pages have many module references (10+), so the "fewest refs per page" heuristic correctly identifies content headers (1 module) over TOC pages.

### 13.3 Manual CSV override (`chapter_modules.csv`)

- A `chapter_modules.csv` file in the project root lets you manually define page ranges for any module by editing `source,module,start_page,end_page`.
- When the CSV exists, `extract_modules()` returns modules from the CSV (with auto-detected titles) and `load_module_docs()` uses the CSV page range directly, bypassing auto-detection.
- When the CSV is absent, both functions fall back to the auto-detection logic described above — zero behavior change.
- Initial CSV is generated from current auto-detected ranges (47 rows across 8 PDFs). Edit it to fix page ranges for poorly-detected modules.

How to edit:
```csv
source,module,start_page,end_page
Care group.pdf,1,12,13
Care group.pdf,2,14,15
```

The entries are inclusive: `start_page=5, end_page=10` includes all chunks with page numbers 5 through 10.

### 13.4 Files changed

- `langgraph_app/services/chapter_mode.py`:
  - `_DANDA_FIX` — OCR danda → digit 1 fix
  - `_MODULE_PATTERN` — regex matching both OCR spellings
  - `_compute_number_map()` — normalizes OCR'd module numbers to clean sequential
  - `_find_colophon_page()` — detects credits page as content boundary
  - `_load_csv_ranges()` — loads manual overrides from CSV
  - `extract_modules()` — module extraction with colophon filter, number normalization, and CSV override
  - `load_module_docs()` — content-boundary detection with CSV short-circuit
  - `_find_source_json()` — shared helper for locating chunk JSON by source name
- `langgraph_app/services/tutor_service.py`:
  - `get_chapter_modules()` — delegates to `extract_modules()`
  - `load_module_docs()` — delegates to chapter_mode version
- `langgraph_app/cli.py` — updated `_run_chapter_mode()` with module selection flow; removed free-text topic prompt; replaced per-segment story calls with single LLM call; story displayed as-is without splitting
- `langgraph_app/services/llm.py` — story prompt updated to forbid lists/headings, require 8–10 paragraphs, and end with a `**കഥയുടെ പാഠം:**` moral paragraph; added `max_tokens` parameter (default 768)
- `chapter_modules.csv` — initial 47-row CSV generated from auto-detected ranges

### 13.5 Validation

- The module overview (`chapter_modules_overview.md`) was regenerated twice — before and after number normalization — to confirm all 8 PDFs produce clean sequential module numbers.
- Load tests verified that every normalized module number (1..N per PDF) returns the correct content pages via `load_module_docs()`.
- CSV/no-CSV fallback tested by temporarily removing the CSV file and confirming auto-detection still works correctly.