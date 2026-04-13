"""Chroma-backed retriever service."""

import asyncio
import logging
import re
from typing import Any

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
from langgraph_app.services.retriever_base import RetrieverBase


logger = logging.getLogger(__name__)


class RAGRetriever(RetrieverBase):
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
        self.db_dir = db_dir
        self.model_name = model_name
        self.candidate_k = max(int(candidate_k), TOP_K)
        self.min_similarity = float(min_similarity)
        self.dedup_max_per_source_page = max(int(dedup_max_per_source_page), 1)
        self.rerank_enabled = bool(rerank_enabled)
        self.hybrid_enabled = bool(hybrid_enabled)

        if not self.validate_config():
            raise ValueError("Invalid retriever configuration")

        try:
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_name,
            )
            client = chromadb.PersistentClient(path=db_dir)
            self.collection = client.get_collection(
                name="malayalam_rag",
                embedding_function=ef,
            )
            logger.info("RAG collection loaded with %s chunks", self.collection.count())
        except Exception as exc:
            logger.exception("Failed to initialize RAGRetriever")
            raise RuntimeError(f"Failed to initialize RAGRetriever: {exc}") from exc

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
        if not question or not question.strip():
            raise ValueError("question must be non-empty")
        if int(top_k) < 1:
            raise ValueError("top_k must be >= 1")

        candidate_k = max(int(top_k), self.candidate_k)
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=candidate_k,
            )
        except Exception as exc:
            logger.exception("RAG query failed")
            raise RuntimeError(f"RAG query failed: {exc}") from exc

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

    async def query_async(self, question: str, top_k: int = TOP_K) -> list[dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.query, question, top_k)

    def add_documents(self, documents: list[str], metadatas: list[dict], ids: list[str]) -> None:
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        except Exception as exc:
            logger.exception("Failed to add documents to collection")
            raise RuntimeError(f"Failed to add documents: {exc}") from exc

    def delete_documents(self, ids: list[str]) -> None:
        try:
            self.collection.delete(ids=ids)
        except Exception as exc:
            logger.exception("Failed to delete documents from collection")
            raise RuntimeError(f"Failed to delete documents: {exc}") from exc

    def clear_collection(self) -> None:
        try:
            existing = self.collection.get(include=[])
            existing_ids = existing.get("ids") or []
            if existing_ids:
                self.collection.delete(ids=existing_ids)
        except Exception as exc:
            logger.exception("Failed to clear collection")
            raise RuntimeError(f"Failed to clear collection: {exc}") from exc

    def get_collection_size(self) -> int:
        try:
            return int(self.collection.count())
        except Exception as exc:
            logger.exception("Failed to read collection size")
            raise RuntimeError(f"Failed to read collection size: {exc}") from exc

    def get_config(self) -> dict[str, Any]:
        return {
            "db_dir": self.db_dir,
            "model_name": self.model_name,
            "candidate_k": self.candidate_k,
            "min_similarity": self.min_similarity,
            "dedup_max_per_source_page": self.dedup_max_per_source_page,
            "rerank_enabled": self.rerank_enabled,
            "hybrid_enabled": self.hybrid_enabled,
            "top_k": TOP_K,
            "collection_name": "malayalam_rag",
        }

    def update_config(self, **kwargs) -> dict[str, Any]:
        for key, value in kwargs.items():
            if key == "candidate_k":
                self.candidate_k = max(int(value), TOP_K)
            elif key == "min_similarity":
                self.min_similarity = float(value)
            elif key == "dedup_max_per_source_page":
                self.dedup_max_per_source_page = max(int(value), 1)
            elif key == "rerank_enabled":
                self.rerank_enabled = bool(value)
            elif key == "hybrid_enabled":
                self.hybrid_enabled = bool(value)
        if not self.validate_config():
            raise ValueError("Invalid configuration update")
        return self.get_config()

    def validate_config(self) -> bool:
        if self.candidate_k < TOP_K:
            return False
        if not (0.0 <= float(self.min_similarity) <= 1.0):
            return False
        if self.dedup_max_per_source_page < 1:
            return False
        return True

    def health_check(self) -> bool:
        try:
            _ = self.collection.count()
            return True
        except Exception:
            return False

    def get_stats(self) -> dict[str, Any]:
        healthy = self.health_check()
        return {
            "chunk_count": self.get_collection_size() if healthy else 0,
            "collection_name": "malayalam_rag",
            "vector_model": self.model_name,
            "healthy": healthy,
        }
