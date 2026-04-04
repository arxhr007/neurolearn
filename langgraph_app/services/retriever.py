"""Chroma-backed retriever service."""

import chromadb
from chromadb.utils import embedding_functions

from langgraph_app.config import TOP_K


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
            docs.append(
                {
                    "text": results["documents"][0][i],
                    "source": results["metadatas"][0][i]["source"],
                    "page": results["metadatas"][0][i]["page"],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                }
            )
        return docs
