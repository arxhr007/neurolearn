"""
Build a ChromaDB vector index from the RAG-ready JSON chunks.

Usage:
    python build_index.py
    python build_index.py --chunks-dir ./output/rag_chunks --db-dir ./vectorstore
"""

import argparse
import json
import os
import sys

import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm

from text_normalization import normalize_ocr_text


def normalize_chunk_text(raw: str) -> str:
    """Normalize OCR-style whitespace before indexing documents."""
    return normalize_ocr_text(raw)


def load_chunks(chunks_dir: str) -> list[dict]:
    """Load all JSON chunk files from the given directory."""
    all_chunks = []
    json_files = sorted(
        f for f in os.listdir(chunks_dir)
        if f.endswith(".json") and f != "_manifest.json"
    )
    if not json_files:
        print(f"No JSON chunk files found in {chunks_dir}")
        sys.exit(1)

    for fname in json_files:
        path = os.path.join(chunks_dir, fname)
        with open(path, "r", encoding="utf-8") as fh:
            chunks = json.load(fh)
            all_chunks.extend(chunks)
        print(f"  Loaded {len(chunks):>4d} chunks from {fname}")

    return all_chunks


def _validate_and_prepare_chunks(raw_chunks: list[dict], min_chars: int = 40) -> tuple[list[dict], dict]:
    """Validate required fields, normalize text, and deduplicate chunk IDs."""
    prepared: list[dict] = []
    stats = {
        "invalid_rows": 0,
        "empty_rows": 0,
        "duplicate_rows": 0,
    }
    seen_ids: set[str] = set()

    for chunk in raw_chunks:
        if not isinstance(chunk, dict):
            stats["invalid_rows"] += 1
            continue

        source = chunk.get("source")
        page = chunk.get("page")
        chunk_id = chunk.get("chunk_id")
        text = normalize_chunk_text(str(chunk.get("text") or ""))

        if not source or page is None or chunk_id is None:
            stats["invalid_rows"] += 1
            continue
        if len(text) < min_chars:
            stats["empty_rows"] += 1
            continue

        doc_id = f"{source}__p{page}_c{chunk_id}"
        if doc_id in seen_ids:
            stats["duplicate_rows"] += 1
            continue

        seen_ids.add(doc_id)
        prepared.append(
            {
                "id": doc_id,
                "text": text,
                "metadata": {
                    "source": source,
                    "page": page,
                    "chunk_id": chunk_id,
                },
            }
        )

    return prepared, stats


def build_index(
    chunks_dir: str,
    db_dir: str,
    model_name: str,
    collection_name: str,
    rebuild: bool,
    min_chars: int,
) -> None:
    """Ingest all chunks into a persistent ChromaDB collection."""
    print(f"\n=== Loading chunks from {chunks_dir} ===")
    chunks = load_chunks(chunks_dir)
    print(f"\nTotal chunks to index: {len(chunks)}")

    # Use a multilingual sentence-transformer model for embeddings
    print(f"\nInitialising embedding model: {model_name}")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=model_name,
    )

    # Persistent ChromaDB
    print(f"Creating/opening ChromaDB at {db_dir}")
    client = chromadb.PersistentClient(path=db_dir)

    if rebuild:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    prepared_chunks, stats = _validate_and_prepare_chunks(chunks, min_chars=min_chars)
    print(
        "Chunk validation: "
        f"kept={len(prepared_chunks)} "
        f"invalid={stats['invalid_rows']} "
        f"short_or_empty={stats['empty_rows']} "
        f"duplicates={stats['duplicate_rows']}"
    )
    if not prepared_chunks:
        print("No valid chunks left to index after validation. Exiting.")
        return

    # Batch insert (ChromaDB max batch = 41666 for safe operation)
    batch_size = 500
    for i in tqdm(range(0, len(prepared_chunks), batch_size), desc="Indexing"):
        batch = prepared_chunks[i : i + batch_size]
        ids = [c["id"] for c in batch]
        documents = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]
        collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"\nDone! Indexed {collection.count()} chunks into '{collection.name}'")
    print(f"Vector store saved to: {os.path.abspath(db_dir)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ChromaDB index from RAG chunks")
    parser.add_argument(
        "--chunks-dir",
        default="./output/rag_chunks",
        help="Directory containing JSON chunk files (default: ./output/rag_chunks)",
    )
    parser.add_argument(
        "--db-dir",
        default="./vectorstore",
        help="Directory for persistent ChromaDB (default: ./vectorstore)",
    )
    parser.add_argument(
        "--model",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="Sentence-transformer model for embeddings",
    )
    parser.add_argument(
        "--collection",
        default="malayalam_rag",
        help="Collection name in ChromaDB (default: malayalam_rag)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and rebuild the target collection from scratch",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=40,
        help="Skip chunks shorter than this length after normalization (default: 40)",
    )
    args = parser.parse_args()
    build_index(
        args.chunks_dir,
        args.db_dir,
        args.model,
        args.collection,
        args.rebuild,
        args.min_chars,
    )


if __name__ == "__main__":
    main()
