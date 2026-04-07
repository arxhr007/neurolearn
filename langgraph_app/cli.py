"""CLI runner for the modular LangGraph runtime."""

import argparse
import os
import sys

from langgraph_app.config import DEFAULT_DB_DIR, DEFAULT_MODEL, STUDENT_DB_PATH, TOP_K
from langgraph_app.graph.builder import build_graph_app
from langgraph_app.services.intent_classifier import IntentClassifier
from langgraph_app.services.llm import MalayalamLLM
from langgraph_app.services.retriever import RAGRetriever
from langgraph_app.services.student_db import StudentDB


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
    app,
    top_k: int,
    student_id: str,
    student_profile: dict,
    student_db: StudentDB,
    llm: MalayalamLLM,
    student_response: str | None = None,
    check_answer_hint: str | None = None,
) -> dict:
    print("\n  Searching knowledge base...")
    response_text = student_response if student_response is not None else question
    payload = {
        "student_id": student_id,
        "student_db": student_db,
        "llm": llm,
        "question": question,
        "student_response": response_text,
        "top_k": top_k,
        "student_profile": student_profile,
    }
    if check_answer_hint:
        payload["check_answer_hint"] = check_answer_hint

    state = app.invoke(payload)

    docs = state.get("docs", [])
    if docs:
        print(f"   Found {len(docs)} relevant passages")
        for i, doc in enumerate(docs, 1):
            dist_str = f" (distance: {doc['distance']:.3f})" if doc.get("distance") is not None else ""
            print(f"   [{i}] {doc['source']} p.{doc['page']}{dist_str}")
    else:
        print("   No relevant passages found.")

    print("\n  Generating Malayalam answer...")
    answer = state.get("answer")
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
    check_question = state.get("check_question")
    if check_question:
        print(f"\n  Check Question:\n\n{check_question}")
    evaluation_result = state.get("evaluation_result")
    if evaluation_result:
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


def run_interactive(
    app,
    top_k: int,
    student_id: str,
    student_profile: dict,
    student_db: StudentDB,
    llm: MalayalamLLM,
) -> None:
    print("\n" + "=" * 60)
    print("  Malayalam RAG System (LangGraph Phase 1)")
    print("  Type 'exit' or 'quit' to stop")
    print("=" * 60 + "\n")

    pending_check_question: str | None = None
    pending_check_answer_hint: str | None = None

    while True:
        try:
            question = input("  Enter question (Malayalam/English): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "stop", "bye"):
            print("\nExiting. Goodbye!")
            break

        if pending_check_question:
            # Treat next user turn as an answer to the last generated check question.
            state = _answer_question(
                pending_check_question,
                app,
                top_k,
                student_id,
                student_profile,
                student_db,
                llm,
                student_response=question,
                check_answer_hint=pending_check_answer_hint,
            )
        else:
            state = _answer_question(question, app, top_k, student_id, student_profile, student_db, llm)

        evaluation_result = state.get("evaluation_result") or {}
        is_correct = evaluation_result.get("is_correct")
        check_question = state.get("check_question")

        if check_question:
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
    app,
    top_k: int,
    student_id: str,
    student_profile: dict,
    student_db: StudentDB,
    llm: MalayalamLLM,
) -> None:
    print(f"\n  Query: {query}")
    _answer_question(query, app, top_k, student_id, student_profile, student_db, llm)


def main() -> None:
    _load_env_file()

    parser = argparse.ArgumentParser(description="Malayalam Text RAG System (LangGraph Phase 1)")
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Single question to answer (non-interactive mode)",
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

    retriever = RAGRetriever(args.db_dir, args.model)
    llm = MalayalamLLM()
    intent_classifier = IntentClassifier(llm.client)
    app = build_graph_app(retriever, llm, intent_classifier)

    if args.text:
        run_single_query(args.text, app, args.top_k, args.student_id, student_profile, student_db, llm)
    else:
        run_interactive(app, args.top_k, args.student_id, student_profile, student_db, llm)
