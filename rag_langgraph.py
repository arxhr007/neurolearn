"""
Malayalam Text RAG System (LangGraph Phase 1)
==============================================
Phase 1 parity runtime that mirrors rag.py behavior using a minimal LangGraph.

Flow:
    Parent Orchestrator -> Knowledge Retriever -> Answer Generator

Usage:
    python rag_langgraph.py
    python rag_langgraph.py --text "പഠന രീതി എന്താണ്"
"""

import argparse
from typing import TypedDict

from langgraph.graph import END, StateGraph

from rag import DEFAULT_DB_DIR, DEFAULT_MODEL, TOP_K, MalayalamLLM, RAGRetriever


class RAGState(TypedDict, total=False):
    question: str
    top_k: int
    docs: list[dict]
    answer: str
    active_node: str


def _build_graph(retriever: RAGRetriever, llm: MalayalamLLM):
    def parent_orchestrator(state: RAGState) -> RAGState:
        return {"active_node": "parent_orchestrator"}

    def knowledge_retriever(state: RAGState) -> RAGState:
        question = state["question"]
        docs = retriever.query(question, top_k=state.get("top_k", TOP_K))
        return {
            "docs": docs,
            "active_node": "knowledge_retriever",
        }

    def answer_generator(state: RAGState) -> RAGState:
        answer = llm.generate(state["question"], state.get("docs", []))
        return {
            "answer": answer,
            "active_node": "answer_generator",
        }

    graph = StateGraph(RAGState)
    graph.add_node("parent_orchestrator", parent_orchestrator)
    graph.add_node("knowledge_retriever", knowledge_retriever)
    graph.add_node("answer_generator", answer_generator)

    graph.set_entry_point("parent_orchestrator")
    graph.add_edge("parent_orchestrator", "knowledge_retriever")
    graph.add_edge("knowledge_retriever", "answer_generator")
    graph.add_edge("answer_generator", END)

    return graph.compile()


def _answer_question(question: str, app, top_k: int) -> None:
    print("\n  Searching knowledge base...")
    state = app.invoke({"question": question, "top_k": top_k})

    docs = state.get("docs", [])
    if docs:
        print(f"   Found {len(docs)} relevant passages")
        for i, d in enumerate(docs, 1):
            dist_str = f" (distance: {d['distance']:.3f})" if d.get("distance") is not None else ""
            print(f"   [{i}] {d['source']} p.{d['page']}{dist_str}")
    else:
        print("   No relevant passages found.")

    print("\n  Generating Malayalam answer...")
    answer = state.get("answer")
    print(f"\n{'─' * 60}")
    print(f"  Answer:\n\n{answer}")
    print(f"{'─' * 60}\n")


def run_interactive(app, top_k: int) -> None:
    print("\n" + "=" * 60)
    print("  Malayalam RAG System (LangGraph Phase 1)")
    print("  Type 'exit' or 'quit' to stop")
    print("=" * 60 + "\n")

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

        _answer_question(question, app, top_k)


def run_single_query(query: str, app, top_k: int) -> None:
    print(f"\n  Query: {query}")
    _answer_question(query, app, top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Malayalam Text RAG System (LangGraph Phase 1)")
    parser.add_argument(
        "--text", type=str, default=None,
        help="Single question to answer (non-interactive mode)",
    )
    parser.add_argument(
        "--db-dir", default=DEFAULT_DB_DIR,
        help=f"ChromaDB directory (default: {DEFAULT_DB_DIR})",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="Embedding model name",
    )
    parser.add_argument(
        "--top-k", type=int, default=TOP_K,
        help=f"Number of chunks to retrieve (default: {TOP_K})",
    )
    args = parser.parse_args()

    print("Initialising components...")
    retriever = RAGRetriever(args.db_dir, args.model)
    llm = MalayalamLLM()
    app = _build_graph(retriever, llm)

    if args.text:
        run_single_query(args.text, app, args.top_k)
    else:
        run_interactive(app, args.top_k)


if __name__ == "__main__":
    main()
