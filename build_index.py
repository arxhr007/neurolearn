"""
Build a ChromaDB vector index from the RAG-ready JSON chunks.

Usage:
    python build_index.py
    python build_index.py --chunks-dir ./output/rag_chunks --db-dir ./vectorstore
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm


_RE_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_RE_PAGE_NUMBER = re.compile(
    r"(?m)^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$"
)
_RE_HEADER_FOOTER = re.compile(
    r"(?m)^.{0,60}(പേജ്|page|PAGE|അധ്യായം|chapter|CHAPTER)\s*\d*.*$",
    re.IGNORECASE,
)


def normalize_chunk_text(raw: str) -> str:
    """Normalize OCR-style whitespace before indexing documents."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\n", "\n").replace("\\r", "\n")
    text = text.replace("\u00a0", " ")
    text = _RE_PAGE_NUMBER.sub("", text)
    text = _RE_HEADER_FOOTER.sub("", text)

    text = re.sub(r"\s+", " ", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


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


def build_index(chunks_dir: str, db_dir: str, model_name: str) -> None:
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

    # Delete existing collection if any, to rebuild cleanly
    try:
        client.delete_collection("malayalam_rag")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name="malayalam_rag",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Batch insert (ChromaDB max batch = 41666 for safe operation)
    batch_size = 500
    for i in tqdm(range(0, len(chunks), batch_size), desc="Indexing"):
        batch = chunks[i : i + batch_size]
        ids = [f"{c['source']}__p{c['page']}_c{c['chunk_id']}" for c in batch]
        documents = [normalize_chunk_text(c["text"]) for c in batch]
        metadatas = [
            {"source": c["source"], "page": c["page"], "chunk_id": c["chunk_id"]}
            for c in batch
        ]
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
    args = parser.parse_args()
    build_index(args.chunks_dir, args.db_dir, args.model)


if __name__ == "__main__":
    main()
