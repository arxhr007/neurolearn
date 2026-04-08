"""Chroma-backed retriever service."""

import re

import chromadb
from chromadb.utils import embedding_functions

from langgraph_app.config import (
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_DEDUP_MAX_PER_SOURCE_PAGE,
    RETRIEVAL_HYBRID_ENABLED,
    RETRIEVAL_MIN_SIMILARITY,
    RETRIEVAL_RERANK_ENABLED,
    TOP_K,
)


class RAGRetriever:
    def __init__(
        self,
        db_dir: str,
        model_name: str,
        candidate_k: int = RETRIEVAL_CANDIDATE_K,
        min_similarity: float = RETRIEVAL_MIN_SIMILARITY,
        dedup_max_per_source_page: int = RETRIEVAL_DEDUP_MAX_PER_SOURCE_PAGE,
        rerank_enabled: bool = RETRIEVAL_RERANK_ENABLED,
        hybrid_enabled: bool = RETRIEVAL_HYBRID_ENABLED,
    ):
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        client = chromadb.PersistentClient(path=db_dir)
        self.collection = client.get_collection(
            name="malayalam_rag",
            embedding_function=ef,
        )
        self.candidate_k = max(int(candidate_k), TOP_K)
        self.min_similarity = float(min_similarity)
        self.dedup_max_per_source_page = max(int(dedup_max_per_source_page), 1)
        self.rerank_enabled = bool(rerank_enabled)
        self.hybrid_enabled = bool(hybrid_enabled)
        print(f"[RAG] Loaded collection with {self.collection.count()} chunks")

    @staticmethod
    def _distance_to_similarity(distance: float | None) -> float:
        # Chroma cosine distance: lower is better. Convert to bounded similarity.
        if distance is None:
            return 0.0
        similarity = 1.0 - float(distance)
        if similarity < 0.0:
            return 0.0
        if similarity > 1.0:
            return 1.0
        return similarity

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"\w+", (text or "").lower()) if len(t) > 1}

    def _lexical_overlap_score(self, question: str, chunk_text: str) -> float:
        q_tokens = self._tokenize(question)
        if not q_tokens:
            return 0.0
        c_tokens = self._tokenize(chunk_text)
        if not c_tokens:
            return 0.0
        overlap = len(q_tokens & c_tokens)
        return overlap / len(q_tokens)

    def _blend_score(self, dense_similarity: float, lexical_score: float) -> float:
        if self.hybrid_enabled:
            return (0.6 * dense_similarity) + (0.4 * lexical_score)
        if self.rerank_enabled:
            return (0.8 * dense_similarity) + (0.2 * lexical_score)
        return dense_similarity

    def query(self, question: str, top_k: int = TOP_K) -> list[dict]:
        candidate_k = max(int(top_k), self.candidate_k)
        results = self.collection.query(
            query_texts=[question],
            n_results=candidate_k,
        )
        candidates: list[dict] = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i] or {}
            text = results["documents"][0][i]
            distance = results["distances"][0][i] if results.get("distances") else None
            dense_similarity = self._distance_to_similarity(distance)
            lexical_score = self._lexical_overlap_score(question, text)
            candidates.append(
                {
                    "text": text,
                    "source": metadata.get("source"),
                    "page": metadata.get("page"),
                    "chunk_id": metadata.get("chunk_id"),
                    "vector_id": results["ids"][0][i],
                    "distance": distance,
                    "similarity_score": dense_similarity,
                    "lexical_score": lexical_score,
                }
            )

        # Quality gate: keep only semantically strong candidates.
        filtered = [c for c in candidates if c["similarity_score"] >= self.min_similarity]
        low_confidence_retrieval = False
        if not filtered:
            filtered = sorted(candidates, key=lambda d: d["similarity_score"], reverse=True)
            low_confidence_retrieval = True

        # Diversity gate: avoid multiple near-duplicates from the same source/page.
        kept: list[dict] = []
        per_source_page: dict[tuple[str, str], int] = {}
        for item in sorted(filtered, key=lambda d: d["similarity_score"], reverse=True):
            source = str(item.get("source") or "")
            page = str(item.get("page") or "")
            key = (source, page)
            current_count = per_source_page.get(key, 0)
            if current_count >= self.dedup_max_per_source_page:
                continue
            per_source_page[key] = current_count + 1
            kept.append(item)

        if self.rerank_enabled or self.hybrid_enabled:
            for item in kept:
                item["blended_score"] = self._blend_score(
                    dense_similarity=float(item.get("similarity_score") or 0.0),
                    lexical_score=float(item.get("lexical_score") or 0.0),
                )
            kept.sort(key=lambda d: d.get("blended_score", 0.0), reverse=True)
        else:
            for item in kept:
                item["blended_score"] = item.get("similarity_score", 0.0)

        docs = kept[: int(top_k)]
        for item in docs:
            item["low_confidence_retrieval"] = low_confidence_retrieval
        return docs
