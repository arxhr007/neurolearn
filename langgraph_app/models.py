"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# Tutor Models
# ============================================================================

class Source(BaseModel):
    """Evidence chunk from retrieval."""
    source: str  # "Care group.pdf"
    page: int
    chunk_id: str
    excerpt: str
    distance: Optional[float] = None  # Retrieval score for observability
    similarity_score: Optional[float] = None


class TutorQuestionRequest(BaseModel):
    """Request: Student asks a question."""
    student_id: str
    conversation_id: str
    question: str
    context: Optional[dict] = Field(None, description="Optional context (active goal, recent mastery)")


class TutorQuestionResponse(BaseModel):
    """Response: Tutor provides answer + check question."""
    conversation_id: str
    turn_id: str
    answer: str
    check_question: Optional[str] = None
    check_answer_hint: Optional[str] = None
    sources: List[Source] = []
    status: str  # "waiting_for_answer", "answered", "error"
    generated_at: datetime


class TutorAnswerRequest(BaseModel):
    """Request: Student submits answer to check question."""
    student_id: str
    conversation_id: str
    turn_id: str
    student_answer: str
    check_answer_hint: Optional[str] = None


class TutorAnswerResponse(BaseModel):
    """Response: Evaluation result + feedback."""
    conversation_id: str
    turn_id: str
    is_correct: bool
    feedback: str
    misconception: Optional[str] = None
    confidence: float  # 0.0 – 1.0
    mastery_event_id: str
    remediation: Optional[str] = None  # If is_correct=False
    status: str  # "evaluated"
    generated_at: datetime


class ConversationTurn(BaseModel):
    """A single turn in a conversation (question, answer, or remediation)."""
    turn_id: str
    type: str  # "question", "answer", "remediation"
    
    # Question turn fields
    question: Optional[str] = None
    answer: Optional[str] = None
    check_question: Optional[str] = None
    check_answer_hint: Optional[str] = None
    sources: Optional[List[Source]] = None
    
    # Answer turn fields
    student_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    feedback: Optional[str] = None
    misconception: Optional[str] = None
    confidence: Optional[float] = None
    mastery_event_id: Optional[str] = None
    remediation: Optional[str] = None
    
    generated_at: datetime


class ConversationResponse(BaseModel):
    """A complete conversation (multi-turn chat history)."""
    conversation_id: str
    student_id: str
    created_at: datetime
    updated_at: datetime
    turns: List[ConversationTurn]
    learning_goal: Optional[str] = None


# ============================================================================
# Student Profile Models
# ============================================================================

class StudentProfileRequest(BaseModel):
    """Request: Create or update student profile."""
    name: str
    learning_style: str  # "analogy-heavy", "visual", "kinesthetic", etc.
    reading_age: int  # 6–18
    interests: List[str] = []
    neuro_profile: List[str] = ["general"]  # ["adhd", "dyslexia", "autism", ...]


class StudentProfile(BaseModel):
    """Response: Student profile data."""
    student_id: str
    name: str
    learning_style: str
    reading_age: int
    interests: List[str]
    neuro_profile: List[str]
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Learning Goals Models
# ============================================================================

class LearningGoalRequest(BaseModel):
    """Request: Create or update learning goal."""
    goal_text: str = Field(..., min_length=1, max_length=500)


class LearningGoal(BaseModel):
    """Response: Learning goal data."""
    goal_id: str
    goal_text: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class LearningGoalsResponse(BaseModel):
    """Response: Student's goals (active + archived)."""
    active: List[LearningGoal] = []
    archived: List[LearningGoal] = []


# ============================================================================
# Mastery Models
# ============================================================================

class MasteryEvent(BaseModel):
    """A single mastery event (answer evaluation)."""
    id: str
    student_id: str
    concept_key: str  # "handwashing:hygiene_importance"
    is_correct: bool
    confidence: float  # 0.0 – 1.0
    misconception: Optional[str] = None
    source_doc: Optional[str] = None
    source_page: Optional[int] = None
    source_chunk_id: Optional[int] = None
    created_at: datetime


class MasteryHistoryResponse(BaseModel):
    """Response: Student's mastery history."""
    total: int
    events: List[MasteryEvent] = []
    limit: int
    offset: int


# ============================================================================
# Admin / Content Management Models
# ============================================================================

class VectorStoreStatus(BaseModel):
    """Vector store state."""
    type: str  # "chroma"
    chunk_count: int
    collection_name: str
    size_mb: float
    last_rebuilt: Optional[datetime] = None


class IngestionJob(BaseModel):
    """PDF ingestion job status."""
    job_id: str
    status: str  # "queued", "in_progress", "completed", "failed"
    pdf_file: str
    progress_percent: int  # 0–100
    chunks_generated: int = 0
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    eta: Optional[datetime] = None


class ContentStatusResponse(BaseModel):
    """Response: Vector store + ingestion job status."""
    vector_store: VectorStoreStatus
    ingestion_jobs: List[IngestionJob] = []


class ContentIngestionRequest(BaseModel):
    """Request: Upload PDF for ingestion."""
    chunk_size: int = 500
    chunk_overlap: int = 100
    workers: int = 4


class ContentIngestionResponse(BaseModel):
    """Response: Ingestion job created."""
    job_id: str
    status: str  # "queued"
    pdf_file: str
    created_at: datetime
    message: str


class RetrieverConfig(BaseModel):
    """Retriever configuration."""
    candidate_k: int
    min_similarity: float
    dedup_max_per_source_page: int
    rerank_enabled: bool
    hybrid_enabled: bool
    top_k: int
    notes: Optional[str] = None


# ============================================================================
# Analytics Models
# ============================================================================

class ConceptPerformance(BaseModel):
    """Performance for a single concept."""
    concept: str
    events: int
    accuracy: float


class CohortPerformance(BaseModel):
    """Performance for a cohort."""
    cohort_id: str
    students: int
    avg_accuracy: float


class AnalyticsResponse(BaseModel):
    """Response: High-level analytics."""
    period: str  # "7d", "30d", "90d"
    total_students: int
    active_students_7d: int
    total_conversations: int
    total_mastery_events: int
    avg_accuracy: float
    top_concepts: List[ConceptPerformance] = []
    cohort_performance: List[CohortPerformance] = []


# ============================================================================
# Health & Error Models
# ============================================================================

class ServiceStatus(BaseModel):
    """Status of a single service."""
    status: str  # "ok", "degraded", "offline"


class HealthResponse(BaseModel):
    """Response: System health check."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    services: dict[str, str] = {  # service_name -> status
        "api": "ok",
        "database": "ok",
        "vector_store": "ok",
        "llm_provider": "ok"
    }


class ErrorDetail(BaseModel):
    """Error detail."""
    field: Optional[str] = None
    reason: str


class ErrorResponse(BaseModel):
    """Structured error response."""
    error: dict = {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An error occurred",
        "details": None,
        "request_id": "req_123"
    }


# ============================================================================
# Auth Models
# ============================================================================

class LoginRequest(BaseModel):
    """Request: User login."""
    email: str
    password: str
    role: str  # "student", "teacher", "admin"


class User(BaseModel):
    """User data."""
    user_id: str
    email: str
    role: str
    name: str
    student_id: Optional[str] = None  # If role=student
    cohort_id: Optional[str] = None  # If role=teacher


class LoginResponse(BaseModel):
    """Response: Login successful."""
    access_token: str
    refresh_token: str
    user: User
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Request: Refresh access token."""
    refresh_token: str


class LogoutResponse(BaseModel):
    """Response: Logout successful."""
    message: str = "Logged out successfully"


# ============================================================================
# Admin User Management Models
# ============================================================================

class CreateUserRequest(BaseModel):
    """Request: Create a new user."""
    email: str
    password: str
    role: str  # "student", "teacher", "admin"
    name: str
    cohort_id: Optional[str] = None
    student_profile: Optional[StudentProfileRequest] = None


class UserListItem(BaseModel):
    """A user in a list."""
    user_id: str
    email: str
    role: str
    name: str
    student_id: Optional[str] = None
    cohort_id: Optional[str] = None
    created_at: datetime


class UsersListResponse(BaseModel):
    """Response: List of users."""
    total: int
    users: List[UserListItem] = []
