"""CLI runner for the modular LangGraph runtime."""

import argparse
import logging
import os
import sys
from uuid import uuid4

from langgraph_app.config import (
    DEFAULT_DB_DIR,
    DEFAULT_MODEL,
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_DEDUP_MAX_PER_SOURCE_PAGE,
    RETRIEVAL_HYBRID_ENABLED,
    RETRIEVAL_MIN_SIMILARITY,
    RETRIEVAL_RERANK_ENABLED,
    STUDENT_DB_PATH,
    TOP_K,
)
from langgraph_app.graph.builder import build_graph_app
from langgraph_app.services.intent_classifier import IntentClassifier
from langgraph_app.services.llm import MalayalamLLM
from langgraph_app.services.retriever import RAGRetriever
from langgraph_app.services.chapter_mode import plan_chapter_session
from langgraph_app.services.student_db import StudentDB
from langgraph_app.services.tutor_service import TutorService, TutorServiceConfig


logger = logging.getLogger(__name__)


def _looks_like_new_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False

    if normalized.endswith("?"):
        return True

    question_starts = (
        "what",
        "why",
        "how",
        "when",
        "where",
        "which",
        "who",
        "what's",
        "why's",
        "what is",
        "why is",
        "how is",
        "how does",
        "എന്ത്",
        "എന്തുകൊണ്ട്",
        "എങ്ങനെ",
        "എപ്പോൾ",
        "എവിടെ",
        "ആരാണ്",
        "ഏത്",
    )
    if normalized.startswith(question_starts):
        return True

    return any(word in normalized for word in (" എന്ത് ", " എന്തുകൊണ്ട് ", " എങ്ങനെ ", " എവിടെ ", " എപ്പോൾ "))


def _is_smalltalk(text: str, service: TutorService | None = None) -> bool:
    """Conservative smalltalk detector combining service heuristics and
    additional lightweight rules to avoid misclassifying short conversational
    replies as answers.
    """
    if not text or not text.strip():
        return False
    normalized = text.strip().lower()

    # Fast accept common greeting/ack patterns (English + Malayalam)
    greetings = (
        "hi",
        "hello",
        "hiya",
        "hey",
        "how are you",
        "how r u",
        "hru",
        "good morning",
        "good afternoon",
        "good evening",
        "what's up",
        "whats up",
        "thank you",
        "thankyou",
        "bye",
        "നമസ്",
        "ഹായ്",
        "ഹലോ",
        "നമസ്കാരം",
        "സുഖമാണോ",
        "നന്ദി",
        "ശരി",
    )
    if any(g in normalized for g in greetings):
        return True

    # If the service provides a smalltalk heuristic, use it as a signal.
    if service is not None:
        try:
            kind = service._smalltalk_kind(normalized)
            if kind:
                return True
        except Exception:
            pass

    # Short utterances (<= 4 tokens) that mostly contain stopwords/polite words
    tokens = [t for t in normalized.split() if t]
    if len(tokens) <= 4:
        # If there are any punctuation markers that look like a genuine question
        # (who/what/why/how keywords), do not treat as smalltalk here.
        if any(tok in ("what", "why", "how", "where", "when", "who", "which") for tok in tokens):
            return False
        return True

    return False


def _load_env_file() -> None:
    """Load environment variables from .env when available."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    # Explicit path keeps behavior predictable when launched from different cwd.
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)


def _answer_question(
    question: str,
    service: TutorService,
    top_k: int,
    student_id: str,
    student_profile: dict,
    conversation_id: str,
    student_response: str | None = None,
    check_answer_hint: str | None = None,
) -> dict:
    try:
        if student_response is None:
            response = service.ask_question(
                question=question,
                student_id=student_id,
                student_profile=student_profile,
                top_k=top_k,
                conversation_id=conversation_id,
            )
        else:
            response = service.evaluate_answer(
                question=question,
                student_answer=student_response,
                student_id=student_id,
                student_profile=student_profile,
                check_answer_hint=check_answer_hint,
                top_k=top_k,
                conversation_id=conversation_id,
            )
    except Exception as exc:
        logger.exception("Failed to process question")
        print(f"\n  ERROR: {exc}\n")
        return {}

    if response.is_error():
        print(f"\n  ERROR: {response.answer or response.remediation_explanation or 'Unable to process request'}\n")
        return response.raw_state or {}

    # If this was handled as smalltalk, just print the answer and return.
    if (response.evaluation_result or {}).get("smalltalk"):
        print(f"\n{'─' * 60}")
        print(f"  Answer:\n\n{response.answer}")
        print(f"{'─' * 60}\n")
        return response.raw_state or {}

    state = response.raw_state or {}

    # Show retrieval info only when we actually ran retrieval.
    print("\n  Searching knowledge base...")

    docs = state.get("docs", [])
    if docs:
        print(f"   Found {len(docs)} relevant passages")
        for i, doc in enumerate(docs, 1):
            dist_str = f" (distance: {doc['distance']:.3f})" if doc.get("distance") is not None else ""
            print(f"   [{i}] {doc['source']} p.{doc['page']}{dist_str}")
    else:
        print("   No direct passages found; using a general answer fallback.")

    print("\n  Generating Malayalam answer...")
    answer = state.get("answer") or response.answer
    if answer is None:
        evaluation_result = state.get("evaluation_result") or {}
        answer = evaluation_result.get("feedback")
    print(f"\n{'─' * 60}")
    print(f"  Answer:\n\n{answer}")
    if docs:
        print("\n  Answer Sources:\n")
        for i, doc in enumerate(docs, 1):
            source = doc.get("source") or "unknown"
            page = doc.get("page") if doc.get("page") is not None else "na"
            chunk_id = doc.get("chunk_id")
            vector_id = doc.get("vector_id") or "na"
            source_base = str(source).replace(".pdf", "")
            json_hint = f"output/rag_chunks/{source_base}.json"
            chunk_part = f"chunk_id={chunk_id}" if chunk_id is not None else f"vector_id={vector_id}"
            print(f"  [{i}] textbook={source}, page={page}, {chunk_part}, json={json_hint}")
    answer_text = str(answer or "")
    check_question = state.get("check_question")
    if getattr(service.llm, "looks_like_refusal", None) and service.llm.looks_like_refusal(answer_text):
        check_question = None
    if check_question:
        print(f"\n  Check Question:\n\n{check_question}")
    evaluation_result = state.get("evaluation_result") or {}
    evaluation_status = evaluation_result.get("status")
    if evaluation_status == "check_question_generated":
        print("\n  Evaluation Result:\n")
        print("  pending: answer the check question above")
    elif evaluation_result:
        print("\n  Evaluation Result:\n")
        print(f"  is_correct: {evaluation_result.get('is_correct')}")
        print(f"  feedback: {evaluation_result.get('feedback')}")
        print(f"  misconception: {evaluation_result.get('misconception')}")
        print(f"  confidence: {evaluation_result.get('confidence')}")
    mastery_event = state.get("mastery_event")
    if mastery_event:
        print("\n  Mastery Event Saved:\n")
        print(f"  id: {mastery_event.get('id')}")
        print(f"  student_id: {mastery_event.get('student_id')}")
        print(f"  concept_key: {mastery_event.get('concept_key')}")
        print(f"  is_correct: {mastery_event.get('is_correct')}")
        print(f"  misconception: {mastery_event.get('misconception')}")
        print(f"  confidence: {mastery_event.get('confidence')}")
    remediation_explanation = state.get("remediation_explanation")
    if remediation_explanation:
        print("\n  Remediation (Try Again):\n")
        print(f"{remediation_explanation}")
    print(f"{'─' * 60}\n")

    return state


def _format_chapter_label(chapter: dict) -> str:
    source = str(chapter.get("source") or "unknown")
    first_page = chapter.get("first_page")
    last_page = chapter.get("last_page")
    page_label = ""
    if first_page is not None and last_page is not None:
        page_label = f" (pages {first_page}-{last_page})"
    elif first_page is not None:
        page_label = f" (page {first_page})"
    return f"{source}{page_label}"


def _run_chapter_mode(
    service: TutorService,
    top_k: int,
    student_id: str,
    student_profile: dict,
) -> None:
    print("\n" + "=" * 60)
    print("  Chapter Mode")
    print("  Choose a chapter. The tutor will then run a short drill harness.")
    print("=" * 60 + "\n")

    chapters = service.list_available_chapters()
    if not chapters:
        print("  No chapter sources found in output/rag_chunks.")
        return

    for idx, chapter in enumerate(chapters, 1):
        print(f"  [{idx}] {_format_chapter_label(chapter)}  ({chapter.get('chunk_count', 0)} chunks)")

    while True:
        choice = input("\n  Choose a chapter number (or type 'back'): ").strip()
        if not choice:
            continue
        if choice.lower() in ("back", "exit", "quit"):
            return
        selected = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(chapters):
                selected = chapters[index]
        else:
            lowered = choice.lower()
            for chapter in chapters:
                if lowered in str(chapter.get("source") or "").lower():
                    selected = chapter
                    break
        if selected is None:
            print("  Invalid chapter selection.")
            continue
        break

    chapter_source = str(selected.get("source") or "")

    # ── Module selection (opt-in sub-chapter) ─────────────────────────
    modules = service.get_chapter_modules(chapter_source)
    selected_module = None
    if modules:
        print(f"\n  Modules found in this PDF ({len(modules)}):")
        for mod in modules:
            print(f"    [{mod['number']}] മൊഡ്യൂള്\u200d {mod['number']}")
        mod_choice = input("\n  Choose a module number (or press Enter to skip): ").strip()
        if mod_choice.isdigit():
            num = int(mod_choice)
            for mod in modules:
                if mod["number"] == num:
                    selected_module = mod
                    break
        if selected_module:
            print(f"  Selected: മൊഡ്യൂള്\u200d {selected_module['number']} – {selected_module.get('title') or ''}")
            chapter_docs = service.load_module_docs(chapter_source, selected_module["number"])
        else:
            chapter_docs = service.load_chapter_docs(chapter_source)
    else:
        print("  No module structure found; using whole PDF as chapter.")
        chapter_docs = service.load_chapter_docs(chapter_source)

    if not chapter_docs:
        print("  No chapter excerpts found for the selected chapter; using general grounding.")

    session_plan = plan_chapter_session(chapter_source, chapter_docs)
    story_segment_count = session_plan.get("story_segments", 3)
    total_questions = session_plan.get("question_count", 3)

    print(
        f"  Session depth: difficulty={session_plan.get('difficulty', 1)}, questions={total_questions}"
    )

    try:
        module_label = f" | Module {selected_module['number']}" if selected_module else ""
        chapter_goal = f"Chapter: {chapter_source}{module_label}"
        service.student_db.create_learning_goal(student_id, chapter_goal)
        print(f"  Active chapter set: {chapter_goal}")
    except Exception:
        logger.exception("Failed to persist chapter goal; continuing without saving it")

    chapter_mode = "learn"
    while True:
        mode_choice = input("  Do you want to learn or revise? (learn/revise): ").strip().lower()
        if not mode_choice:
            chapter_mode = "learn"
            break
        if mode_choice in ("learn", "l", "1"):
            chapter_mode = "learn"
            break
        if mode_choice in ("revise", "r", "2"):
            chapter_mode = "revise"
            break
        print("  Please type learn or revise.")

    if chapter_mode == "learn":
        print("\n  Learning mode: we will explain using a story first.")
        combined_text = "\n\n".join(
            str(doc.get("text") or "") for doc in chapter_docs if doc
        )
        try:
            story_text = service.llm.generate_story_from_answer(
                answer=combined_text or chapter_source,
                question=f"{chapter_source} | Module {selected_module['number'] if selected_module else ''}",
                context_docs=chapter_docs[:3],
                student_profile=student_profile,
                max_tokens=4096,
            )
        except Exception:
            logger.exception("Failed to generate learning story")
            story_text = ""

        if story_text:
            print(f"\n  Story:")
            print(f"  {story_text}")
        else:
            print("  Could not generate a story.")
    else:
        print("\n  Revision mode: we will check mastery and focus on simpler review questions.")
        try:
            stats = service.get_mastery_stats(student_id)
            print(f"  Current mastery stats: {stats}")
        except Exception:
            logger.exception("Failed to load mastery stats for revision mode")

    correct_count = 0
    previous_questions: list[str] = []
    chapter_conversation_id = str(uuid4())

    for question_index in range(1, total_questions + 1):
        review_focus = None
        if chapter_mode == "revise":
            review_focus = "Review the same concept more simply."
        elif previous_questions and correct_count < question_index - 1:
            review_focus = "Review the same concept more simply."

        module_label = f" – മൊഡ്യൂള്‍ {selected_module['number']}" if selected_module else ""
        bundle = service.generate_chapter_drill_bundle(
            chapter_name=f"{chapter_source}{module_label}",
            topic=chapter_source,
            chapter_docs=chapter_docs,
            student_profile=student_profile,
            question_index=question_index,
            total_questions=total_questions,
            previous_questions=previous_questions,
            review_focus=review_focus,
        )
        practice_question = str(bundle.get("question") or f"{chapter_source} എന്താണ്?".strip())
        expected_answer = str(bundle.get("expected_answer") or chapter_source)

        print(f"\n  Chapter Question {question_index}/{total_questions}:")
        print(f"  {practice_question}")
        try:
            student_answer = input("  Your answer: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Leaving chapter mode.")
            return

        if student_answer.lower() in ("exit", "quit", "stop", "back"):
            print("  Leaving chapter mode.")
            return

        state = _answer_question(
            practice_question,
            service,
            top_k,
            student_id,
            student_profile,
            chapter_conversation_id,
            student_response=student_answer,
            check_answer_hint=expected_answer,
        )
        evaluation_result = state.get("evaluation_result") or {}
        is_correct = bool(evaluation_result.get("is_correct"))
        if is_correct:
            correct_count += 1
        previous_questions.append(practice_question)

        print(f"  Chapter progress: {correct_count}/{question_index} correct")
        if not is_correct:
            print("  Review priority: we will focus on this concept again next.")
        mastery_event = state.get("mastery_event")
        if mastery_event:
            print(f"  Mastery event: {mastery_event.get('concept_key')} | correct={mastery_event.get('is_correct')}")

    print("\n  Chapter drill complete.")
    stats = service.get_mastery_stats(student_id)
    print(f"  Current mastery stats: {stats}")


def run_interactive(
    service: TutorService,
    top_k: int,
    student_id: str,
    student_profile: dict,
) -> None:
    print("\n" + "=" * 60)
    print("  Malayalam RAG System (LangGraph Phase 1)")
    print("  Type 'exit' or 'quit' to stop")
    print("=" * 60 + "\n")

    pending_check_question: str | None = None
    pending_check_answer_hint: str | None = None
    conversation_id = str(uuid4())
    last_state: dict | None = None
    last_question_for_state: str | None = None

    while True:
        prompt = "  Enter question (Malayalam/English): "
        if pending_check_question:
            prompt = "  Enter answer for the check question (or type a new question): "

        try:
            question = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            continue
        # Handle the opt-in story command immediately and always use the saved
        # last_state when available. This prevents re-running the graph when
        # the user simply wants a storyified version of the most recent answer.
        if question.lower().strip() == "story":
            if not last_state:
                print("  No previous answer available to convert. Ask a question first.")
                continue
            try:
                # Use only the saved last_state; do NOT re-run the graph or retrieval.
                story = service.generate_story_from_state(last_state, student_id, student_profile)
                print(f"\n{'─' * 60}")
                print("  Story Version (Malayalam):\n")
                print(story)
                print(f"{'─' * 60}\n")
            except Exception as exc:
                logger.exception("Story generation failed")
                print(f"  ERROR generating story: {exc}")
            continue

        if question.lower().strip() == "chapter":
            _run_chapter_mode(service, top_k, student_id, student_profile)
            continue

        # If a check question is pending, prefer handling smalltalk first
        # so brief conversational replies don't accidentally clear the pending
        # check question even if they look like questions (e.g., "how are you?").
        if pending_check_question:
            if _is_smalltalk(question, service):
                try:
                    resp = service.ask_question(
                        question=question,
                        student_id=student_id,
                        student_profile=student_profile,
                        top_k=top_k,
                        conversation_id=conversation_id,
                    )
                    if (resp.evaluation_result or {}).get("smalltalk"):
                        print(f"\n{'─' * 60}")
                        print(f"  Answer:\n\n{resp.answer}")
                        print(f"{'─' * 60}\n")
                        # Reminder to user to continue with the pending check question.
                        if pending_check_question:
                            print("  Reminder: please answer the pending check question below.")
                            print(f"\n  Check Question:\n\n{pending_check_question}\n")
                except Exception:
                    logger.exception("Failed to handle smalltalk during pending check")
                # Keep the pending check question active and re-prompt.
                continue
        if question.lower() in ("exit", "quit", "stop", "bye"):
            print("\nExiting. Goodbye!")
            break

        if pending_check_question and not _looks_like_new_question(question):
            # If the input looks like smalltalk (greeting/ack), handle it as
            # smalltalk and do NOT treat it as an answer to the pending check
            # question. The pending check remains active.
            smalltalk_kind = None
            try:
                smalltalk_kind = service._smalltalk_kind(question) if hasattr(service, "_smalltalk_kind") else None
            except Exception:
                smalltalk_kind = None

            if smalltalk_kind:
                # Handle smalltalk via the normal ask_question path so the
                # smalltalk heuristics and response rendering are used. Keep
                # the pending check question unchanged.
                try:
                    resp = service.ask_question(
                        question=question,
                        student_id=student_id,
                        student_profile=student_profile,
                        top_k=top_k,
                        conversation_id=conversation_id,
                    )
                    if (resp.evaluation_result or {}).get("smalltalk"):
                        print(f"\n{'─' * 60}")
                        print(f"  Answer:\n\n{resp.answer}")
                        print(f"{'─' * 60}\n")
                        # After responding, remind the user to answer the pending question.
                        if pending_check_question:
                            print("  Reminder: please answer the pending check question below.")
                            print(f"\n  Check Question:\n\n{pending_check_question}\n")
                except Exception:
                    logger.exception("Failed to handle smalltalk during pending check")
                # leave pending_check_question intact
                continue

            # Treat short follow-up text as an answer to the last generated check question.
            call_question = pending_check_question
            state = _answer_question(
                call_question,
                service,
                top_k,
                student_id,
                student_profile,
                conversation_id,
                student_response=question,
                check_answer_hint=pending_check_answer_hint,
            )
        else:
            if pending_check_question:
                print("  Detected a new question; clearing the pending check question.")
                pending_check_question = None
                pending_check_answer_hint = None
            call_question = question
            state = _answer_question(question, service, top_k, student_id, student_profile, conversation_id)

        # Save the last state/question so story mode can operate separately.
        last_state = state
        last_question_for_state = call_question

        evaluation_result = state.get("evaluation_result") or {}
        is_correct = evaluation_result.get("is_correct")
        check_question = state.get("check_question")
        answer_text = str(state.get("answer") or "")

        if check_question and not state.get("general_answer_fallback") and not (getattr(service.llm, "looks_like_refusal", None) and service.llm.looks_like_refusal(answer_text)):
            pending_check_question = check_question
            pending_check_answer_hint = state.get("check_answer_hint")
            print("  Next: answer the check question above.")
        elif is_correct is True:
            pending_check_question = None
            pending_check_answer_hint = None
        elif is_correct is False and pending_check_question:
            print("  Try answering the same check question again.")


def run_single_query(
    query: str,
    service: TutorService,
    top_k: int,
    student_id: str,
    student_profile: dict,
    story: bool = False,
) -> None:
    print(f"\n  Query: {query}")
    state = _answer_question(query, service, top_k, student_id, student_profile, str(uuid4()))
    if story:
        try:
            story_text = service.generate_story_from_state(state, student_id, student_profile)
            print(f"\n{'─' * 60}")
            print("  Story Version (Malayalam):\n")
            print(story_text)
            print(f"{'─' * 60}\n")
        except Exception:
            logger.exception("Story generation failed for single-query mode")


def main() -> None:
    _load_env_file()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Malayalam Text RAG System (LangGraph Phase 1)")
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single question to answer (non-interactive mode)",
    )
    parser.add_argument(
        "--story",
        dest="story",
        action="store_true",
        default=False,
        help="When used with --text, also print a storyified version of the answer",
    )
    parser.add_argument(
        "--chapter-mode",
        dest="chapter_mode",
        action="store_true",
        default=False,
        help="Start an opt-in chapter drill session instead of a regular one-shot query",
    )
    parser.add_argument(
        "--db-dir",
        default=DEFAULT_DB_DIR,
        help=f"ChromaDB directory (default: {DEFAULT_DB_DIR})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Embedding model name",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help=f"Number of chunks to retrieve (default: {TOP_K})",
    )
    parser.add_argument(
        "--retrieval-candidate-k",
        type=int,
        default=RETRIEVAL_CANDIDATE_K,
        help=f"Candidate pool size before filtering/rerank (default: {RETRIEVAL_CANDIDATE_K})",
    )
    parser.add_argument(
        "--retrieval-min-similarity",
        type=float,
        default=RETRIEVAL_MIN_SIMILARITY,
        help=f"Minimum dense similarity to keep a chunk (default: {RETRIEVAL_MIN_SIMILARITY})",
    )
    parser.add_argument(
        "--retrieval-max-per-source-page",
        type=int,
        default=RETRIEVAL_DEDUP_MAX_PER_SOURCE_PAGE,
        help=(
            "Max chunks kept from same source+page after dedup "
            f"(default: {RETRIEVAL_DEDUP_MAX_PER_SOURCE_PAGE})"
        ),
    )
    parser.add_argument(
        "--retrieval-rerank",
        dest="retrieval_rerank",
        action="store_true",
        default=RETRIEVAL_RERANK_ENABLED,
        help=f"Enable lexical+dense rerank (default: {RETRIEVAL_RERANK_ENABLED})",
    )
    parser.add_argument(
        "--no-retrieval-rerank",
        dest="retrieval_rerank",
        action="store_false",
        help="Disable lexical+dense rerank",
    )
    parser.add_argument(
        "--retrieval-hybrid",
        dest="retrieval_hybrid",
        action="store_true",
        default=RETRIEVAL_HYBRID_ENABLED,
        help=f"Enable stronger lexical+dense blend (default: {RETRIEVAL_HYBRID_ENABLED})",
    )
    parser.add_argument(
        "--no-retrieval-hybrid",
        dest="retrieval_hybrid",
        action="store_false",
        help="Disable hybrid lexical+dense blend",
    )
    parser.add_argument(
        "--student-id",
        required=True,
        help="Student ID to load profile from SQLite",
    )
    parser.add_argument(
        "--student-db",
        default=STUDENT_DB_PATH,
        help=f"SQLite student DB path (default: {STUDENT_DB_PATH})",
    )
    args = parser.parse_args()

    print("Initialising components...")
    student_db = StudentDB(args.student_db)
    student_profile = student_db.get_student_profile(args.student_id)
    if not student_profile:
        print(f"ERROR: Student ID not found in DB: {args.student_id}")
        print("Use manage_student_db.py to add a profile first.")
        sys.exit(1)

    retriever = RAGRetriever(
        args.db_dir,
        args.model,
        candidate_k=args.retrieval_candidate_k,
        min_similarity=args.retrieval_min_similarity,
        dedup_max_per_source_page=args.retrieval_max_per_source_page,
        rerank_enabled=args.retrieval_rerank,
        hybrid_enabled=args.retrieval_hybrid,
    )
    try:
        llm = MalayalamLLM()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    intent_classifier = IntentClassifier(llm.client)
    app = build_graph_app(retriever, llm, intent_classifier)
    service = TutorService(
        graph=app,
        retriever=retriever,
        student_db=student_db,
        llm=llm,
        config=TutorServiceConfig(default_top_k_retrieval=args.top_k),
    )

    if args.chapter_mode:
        _run_chapter_mode(service, args.top_k, args.student_id, student_profile)
    elif args.text:
        run_single_query(args.text, service, args.top_k, args.student_id, student_profile, story=args.story)
    else:
        run_interactive(service, args.top_k, args.student_id, student_profile)
