"""Abstract base class for student database implementations."""

from abc import ABC, abstractmethod
from typing import Optional, Any


class StudentDBBase(ABC):
    """
    Abstract interface for student storage (profile, goals, mastery events).
    
    Allows plugging in different implementations: SQLite (dev), PostgreSQL (prod), etc.
    """

    # ========================================================================
    # Student Profile Methods
    # ========================================================================

    @abstractmethod
    def get_student_profile(self, student_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve a student's profile by ID.
        
        Args:
            student_id: Unique student identifier.
        
        Returns:
            Dict with keys: student_id, name, learning_style, reading_age,
            interest_graph, neuro_profile, created_at, updated_at.
            None if not found.
        """
        pass

    @abstractmethod
    def upsert_student(
        self,
        student_id: str,
        name: str,
        learning_style: str,
        reading_age: int,
        interest_graph: list[str],
        neuro_profile: Optional[list[str]] = None,
    ) -> None:
        """
        Create or update a student profile.
        
        Args:
            student_id: Unique student identifier.
            name: Student name.
            learning_style: E.g., "analogy-heavy", "visual".
            reading_age: Age/grade level (6–18).
            interest_graph: List of interests (e.g., ["chess", "football"]).
            neuro_profile: List of neurodivergent profiles (default: ["general"]).
        """
        pass

    @abstractmethod
    def list_students(self) -> list[dict[str, Any]]:
        """
        List all students.
        
        Returns:
            List of student profile dicts.
        """
        pass

    # ========================================================================
    # Learning Goals Methods
    # ========================================================================

    @abstractmethod
    def get_active_learning_goal(self, student_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve the currently active learning goal for a student.
        
        Args:
            student_id: Unique student identifier.
        
        Returns:
            Dict with keys: id, student_id, goal_text, is_active, created_at, updated_at.
            None if no active goal.
        """
        pass

    @abstractmethod
    def get_learning_goals(self, student_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all learning goals for a student (active and archived).
        
        Args:
            student_id: Unique student identifier.
        
        Returns:
            List of goal dicts, ordered by updated_at DESC.
        """
        pass

    @abstractmethod
    def create_learning_goal(self, student_id: str, goal_text: str) -> dict[str, Any]:
        """
        Create a new learning goal for a student.
        
        Args:
            student_id: Unique student identifier.
            goal_text: Description of the learning goal.
        
        Returns:
            Created goal dict with id, created_at, etc.
        """
        pass

    @abstractmethod
    def update_learning_goal(
        self, student_id: str, goal_id: str, goal_text: Optional[str] = None, is_active: Optional[bool] = None
    ) -> dict[str, Any]:
        """
        Update a learning goal.
        
        Args:
            student_id: Unique student identifier.
            goal_id: Unique goal identifier.
            goal_text: New goal text (optional).
            is_active: Active status (optional).
        
        Returns:
            Updated goal dict.
        """
        pass

    @abstractmethod
    def delete_learning_goal(self, student_id: str, goal_id: str) -> None:
        """
        Delete (soft delete / archive) a learning goal.
        
        Args:
            student_id: Unique student identifier.
            goal_id: Unique goal identifier.
        """
        pass

    # ========================================================================
    # Mastery Events Methods
    # ========================================================================

    @abstractmethod
    def record_mastery_event(
        self,
        student_id: str,
        concept_key: str,
        is_correct: bool,
        misconception: str,
        confidence: float,
        source_doc: Optional[str] = None,
        source_page: Optional[int] = None,
        source_chunk_id: Optional[int] = None,
    ) -> int:
        """
        Record a mastery event (answer evaluation).
        
        Args:
            student_id: Unique student identifier.
            concept_key: Semantic concept key (e.g., "handwashing:hygiene_importance").
            is_correct: Whether the answer was correct.
            misconception: Description of misconception (if any).
            confidence: LLM confidence score (0.0–1.0).
            source_doc: Source document name (e.g., "Care group.pdf").
            source_page: Source page number.
            source_chunk_id: Source chunk ID.
        
        Returns:
            Event ID (auto-generated).
        """
        pass

    @abstractmethod
    def get_mastery_events(
        self,
        student_id: str,
        limit: int = 20,
        offset: int = 0,
        concept_key: Optional[str] = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        Retrieve mastery events for a student.
        
        Args:
            student_id: Unique student identifier.
            limit: Max number of events to return.
            offset: Pagination offset.
            concept_key: Optional filter by concept.
        
        Returns:
            Tuple of (total_count, events_list).
        """
        pass

    @abstractmethod
    def get_mastery_stats(self, student_id: str, recent_days: int = 7) -> dict[str, Any]:
        """
        Get aggregated mastery statistics for a student.
        
        Args:
            student_id: Unique student identifier.
            recent_days: Window for "recent" stats.
        
        Returns:
            Dict with stats like total_events, accuracy, concepts_attempted, etc.
        """
        pass

    # ========================================================================
    # Profile Update Metadata
    # ========================================================================

    @abstractmethod
    def get_last_profile_update_event_id(self, student_id: str) -> int:
        """
        Get the last event ID that triggered a profile update.
        
        Used for guarded profile updates (e.g., only update after N new mastery events).
        
        Args:
            student_id: Unique student identifier.
        
        Returns:
            Event ID (0 if never updated).
        """
        pass

    @abstractmethod
    def set_last_profile_update_event_id(self, student_id: str, event_id: int) -> None:
        """
        Set the last event ID that triggered a profile update.
        
        Args:
            student_id: Unique student identifier.
            event_id: Event ID.
        """
        pass

    # ========================================================================
    # Connection / Lifecycle
    # ========================================================================

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the database is accessible.
        
        Returns:
            True if healthy, False otherwise.
        """
        pass
