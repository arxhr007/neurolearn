"""Abstract base class for retriever implementations."""

from abc import ABC, abstractmethod
from typing import Optional


class RetrieverBase(ABC):
    """
    Abstract interface for document retrieval (RAG backend).
    
    Allows plugging in different implementations: Chroma (local), Pinecone,
    Weaviate, etc.
    """

    # ========================================================================
    # Query Methods
    # ========================================================================

    @abstractmethod
    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """
        Query the vector store for relevant chunks.
        
        Args:
            question: User question (can be Malayalam or English).
            top_k: Maximum number of results to return.
        
        Returns:
            List of result dicts, each with keys:
            - text: Chunk text
            - source: Document name (e.g., "Care group.pdf")
            - page: Page number
            - chunk_id: Unique chunk identifier
            - vector_id: Vector store ID
            - distance: Raw distance score (lower is better for cosine)
            - similarity_score: Normalized similarity (0.0–1.0)
            - lexical_score: Lexical overlap score
            - blended_score: Final combined score (if reranking enabled)
            - low_confidence_retrieval: Flag if result is below confidence threshold
        """
        pass

    @abstractmethod
    def query_async(self, question: str, top_k: int = 5) -> list[dict]:
        """
        Async version of query (useful for non-blocking I/O in web handlers).
        
        Args:
            question: User question.
            top_k: Maximum number of results.
        
        Returns:
            List of result dicts (same format as query()).
        """
        pass

    # ========================================================================
    # Collection Management
    # ========================================================================

    @abstractmethod
    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """
        Add documents (chunks) to the vector store.
        
        Args:
            documents: List of chunk texts.
            metadatas: List of metadata dicts (keys: source, page, chunk_id).
            ids: List of unique IDs for each chunk.
        """
        pass

    @abstractmethod
    def delete_documents(self, ids: list[str]) -> None:
        """
        Delete documents from the vector store.
        
        Args:
            ids: List of document IDs to delete.
        """
        pass

    @abstractmethod
    def clear_collection(self) -> None:
        """
        Clear all documents from the collection (use with caution).
        """
        pass

    @abstractmethod
    def get_collection_size(self) -> int:
        """
        Get the number of documents in the collection.
        
        Returns:
            Document count.
        """
        pass

    # ========================================================================
    # Configuration
    # ========================================================================

    @abstractmethod
    def get_config(self) -> dict:
        """
        Get current retriever configuration.
        
        Returns:
            Dict with keys like:
            - candidate_k: Candidate pool size
            - min_similarity: Minimum similarity threshold
            - dedup_max_per_source_page: Deduplication limit
            - rerank_enabled: Whether reranking is on
            - hybrid_enabled: Whether hybrid scoring is on
            - top_k: Default top-k
        """
        pass

    @abstractmethod
    def update_config(self, **kwargs) -> dict:
        """
        Update retriever configuration.
        
        Args:
            **kwargs: Config keys to update (candidate_k, min_similarity, etc.).
        
        Returns:
            Updated config dict.
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Check if current configuration is valid.
        
        Returns:
            True if valid, False otherwise.
        """
        pass

    # ========================================================================
    # Health & Diagnostics
    # ========================================================================

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the vector store is accessible.
        
        Returns:
            True if healthy, False otherwise.
        """
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """
        Get diagnostic stats about the vector store.
        
        Returns:
            Dict with keys like:
            - chunk_count: Total documents
            - collection_name: Collection name
            - size_mb: Approximate size in MB
            - last_rebuilt: Timestamp of last rebuild
            - vector_model: Embedding model name
        """
        pass
