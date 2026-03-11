"""
Malayalam Text RAG System
==========================
1. Takes Malayalam/English text input
2. Queries the ChromaDB vector store for relevant chunks
3. Sends context + question to Groq LLM for a Malayalam answer
4. Displays the answer

Usage:
    python rag.py                                    # interactive mode
    python rag.py --text "പഠന രീതി എന്താണ്"          # single query

Prerequisites:
    - GROQ_API_KEY env variable
    - ChromaDB index built via build_index.py
"""

import argparse
import os
import sys
import time

import chromadb
from chromadb.utils import embedding_functions
from groq import Groq


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_DB_DIR = "./vectorstore"
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GROQ_MODEL = "openai/gpt-oss-120b"
TOP_K = 5

SYSTEM_PROMPT = """You are a helpful assistant that answers questions in Malayalam.
You will be given context passages extracted from Malayalam educational documents.
Use ONLY the provided context to answer the question. If the context does not
contain enough information, say so honestly in Malayalam.

Rules:
- Always reply in Malayalam script (Unicode).
- Be concise and accurate.
- Cite which source document the information comes from when possible.
- If the question is in Malayalam, answer in Malayalam.
- If the question is in English, still answer in Malayalam but you may include
  the English term in parentheses for clarity."""


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
class RAGRetriever:

    def __init__(self, db_dir: str, model_name: str):
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        client = chromadb.PersistentClient(path=db_dir)
        self.collection = client.get_collection(
            name="malayalam_rag",
            embedding_function=ef,
        )
        print(f"[RAG] Loaded collection with {self.collection.count()} chunks")

    def query(self, question: str, top_k: int = TOP_K) -> list[dict]:
        results = self.collection.query(
            query_texts=[question],
            n_results=top_k,
        )
        docs = []
        for i in range(len(results["ids"][0])):
            docs.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "page": results["metadatas"][0][i]["page"],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return docs


# ---------------------------------------------------------------------------
# LLM (Groq API)
# ---------------------------------------------------------------------------
class MalayalamLLM:

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("ERROR: Set the GROQ_API_KEY environment variable.")
            print("  Get a free key at https://console.groq.com/keys")
            sys.exit(1)
        self.client = Groq(api_key=api_key)
        print(f"[LLM] Using Groq model: {GROQ_MODEL}")

    def generate(self, question: str, context_docs: list[dict]) -> str:
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\n{doc['text']}"
            )
        context_block = "\n\n".join(context_parts)

        user_prompt = f"Context:\n{context_block}\n\nQuestion: {question}\n\nAnswer in Malayalam:"

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------
def run_interactive(retriever: RAGRetriever, llm: MalayalamLLM, top_k: int) -> None:
    print("\n" + "=" * 60)
    print("  Malayalam RAG System")
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

        _answer_question(question, retriever, llm, top_k)


def run_single_query(query: str, retriever: RAGRetriever, llm: MalayalamLLM, top_k: int) -> None:
    print(f"\n  Query: {query}")
    _answer_question(query, retriever, llm, top_k)


def _answer_question(question: str, retriever: RAGRetriever, llm: MalayalamLLM, top_k: int) -> None:
    print("\n  Searching knowledge base...")
    docs = retriever.query(question, top_k=top_k)
    if docs:
        print(f"   Found {len(docs)} relevant passages")
        for i, d in enumerate(docs, 1):
            dist_str = f" (distance: {d['distance']:.3f})" if d['distance'] is not None else ""
            print(f"   [{i}] {d['source']} p.{d['page']}{dist_str}")
    else:
        print("   No relevant passages found.")

    print("\n  Generating Malayalam answer...")
    try:
        answer = llm.generate(question, docs)
    except Exception as e:
        print(f"   LLM error: {e}")
        return

    print(f"\n{'─' * 60}")
    print(f"  Answer:\n\n{answer}")
    print(f"{'─' * 60}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Malayalam Text RAG System")
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

    if args.text:
        run_single_query(args.text, retriever, llm, args.top_k)
    else:
        run_interactive(retriever, llm, args.top_k)


if __name__ == "__main__":
    main()
