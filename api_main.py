"""FastAPI web application for NeuroLearn (Phase 4)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from langgraph_app.config import DEFAULT_DB_DIR, DEFAULT_MODEL, STUDENT_DB_PATH, TOP_K
from langgraph_app.graph.builder import build_graph_app
from langgraph_app.models import (
    ConversationResponse,
    HealthResponse,
    LearningGoal,
    LearningGoalRequest,
    LearningGoalsResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MasteryEvent,
    MasteryHistoryResponse,
    RefreshRequest,
    RetrieverConfig,
    StudentProfile,
    StudentProfileRequest,
    TutorAnswerRequest,
    TutorAnswerResponse,
    TutorQuestionRequest,
    TutorQuestionResponse,
    User,
)
from langgraph_app.services.intent_classifier import IntentClassifier
from langgraph_app.services.llm import MalayalamLLM
from langgraph_app.services.retriever import RAGRetriever
from langgraph_app.services.student_db import StudentDB
from langgraph_app.services.tutor_service import TutorService, TutorServiceConfig


logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Settings(BaseSettings):
    """App settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    api_title: str = "NeuroLearn Tutor API"
    api_version: str = "0.4.0"
    api_description: str = "REST API for adaptive AI-powered tutoring"

    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    groq_api_key: str = ""

    cors_origins_raw: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"

    graph_checkpoint_dir: str = "./checkpoints"
    tutor_response_timeout: int = 30

    student_db_path: str = STUDENT_DB_PATH
    retriever_db_dir: str = DEFAULT_DB_DIR
    retriever_model_name: str = DEFAULT_MODEL

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    student_id: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _load_runtime_env() -> None:
    """Load local .env values into process environment for non-settings consumers."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_path, override=False)
    except Exception:
        logger.warning("Unable to load .env via python-dotenv", exc_info=True)


def _dev_users() -> dict[str, dict[str, Any]]:
    # Dev bootstrap identities for local API testing.
    return {
        "student@neurolearn.local": {
            "user_id": "user_student_1",
            "email": "student@neurolearn.local",
            "name": "Student User",
            "role": "student",
            "student_id": "s100",
            "password": "student123",
        },
        "teacher@neurolearn.local": {
            "user_id": "user_teacher_1",
            "email": "teacher@neurolearn.local",
            "name": "Teacher User",
            "role": "teacher",
            "student_id": None,
            "password": "teacher123",
        },
        "admin@neurolearn.local": {
            "user_id": "user_admin_1",
            "email": "admin@neurolearn.local",
            "name": "Admin User",
            "role": "admin",
            "student_id": None,
            "password": "admin123",
        },
    }


@lru_cache(maxsize=1)
def _service_bundle() -> tuple[TutorService, StudentDB, RAGRetriever]:
    _load_runtime_env()
    settings = get_settings()
    if not os.getenv("GROQ_API_KEY") and settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key

    student_db = StudentDB(settings.student_db_path)
    retriever = RAGRetriever(settings.retriever_db_dir, settings.retriever_model_name)
    llm = MalayalamLLM()
    intent_classifier = IntentClassifier(llm.client)
    graph = build_graph_app(retriever, llm, intent_classifier, checkpoint_path=settings.graph_checkpoint_dir)
    service = TutorService(
        graph=graph,
        retriever=retriever,
        student_db=student_db,
        llm=llm,
        config=TutorServiceConfig(
            default_top_k_retrieval=TOP_K,
            default_response_timeout_seconds=max(int(settings.tutor_response_timeout), 1),
            enable_conversation_history=True,
        ),
    )
    return service, student_db, retriever


def get_tutor_service() -> TutorService:
    try:
        return _service_bundle()[0]
    except SystemExit as exc:
        raise HTTPException(status_code=503, detail="Tutor service unavailable: missing GROQ_API_KEY") from exc
    except Exception as exc:
        logger.exception("Tutor service initialization failed")
        raise HTTPException(status_code=503, detail=f"Tutor service unavailable: {exc}") from exc


def get_tutor_service_optional() -> TutorService | None:
    try:
        return _service_bundle()[0]
    except Exception:
        return None


def get_student_db() -> StudentDB:
    return _service_bundle()[1]


def get_retriever() -> RAGRetriever:
    return _service_bundle()[2]


def _create_token(user: dict[str, Any], expires_minutes: int) -> str:
    settings = get_settings()
    exp = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {
        "sub": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "student_id": user.get("student_id"),
        "exp": exp,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> TokenData:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return TokenData(
        user_id=str(payload.get("sub")),
        email=str(payload.get("email")),
        role=str(payload.get("role")),
        student_id=payload.get("student_id"),
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    creds_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = _decode_token(token)
    except JWTError as exc:
        raise creds_exception from exc

    if not token_data.user_id or not token_data.email or not token_data.role:
        raise creds_exception
    return token_data


def require_roles(*roles: str):
    async def _checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return _checker


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.utcnow()


def _map_student_profile(profile: dict[str, Any]) -> StudentProfile:
    return StudentProfile(
        student_id=profile["student_id"],
        name=profile.get("name") or "",
        learning_style=profile.get("learning_style") or "general",
        reading_age=int(profile.get("reading_age") or 8),
        interests=list(profile.get("interest_graph") or []),
        neuro_profile=list(profile.get("neuro_profile") or ["general"]),
        created_at=_as_dt(profile.get("created_at")),
        updated_at=_as_dt(profile.get("updated_at")),
    )


def _find_question_context(conversation: ConversationResponse, turn_id: str) -> tuple[str, str | None]:
    for turn in conversation.turns:
        if turn.turn_id == turn_id and turn.type == "question":
            return (turn.question or "", turn.check_answer_hint)
    for turn in reversed(conversation.turns):
        if turn.type == "question" and turn.question:
            return (turn.question, turn.check_answer_hint)
    return ("", None)


settings = get_settings()
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Meta"])
def root() -> dict[str, str]:
    return {"name": settings.api_title, "version": settings.api_version, "docs": "/api/docs"}


@app.get("/api/health", response_model=HealthResponse, tags=["Meta"])
def health(service: TutorService | None = Depends(get_tutor_service_optional)) -> HealthResponse:
    services = {
        "api": "ok",
        "database": "ok",
        "vector_store": "ok",
        "llm_provider": "ok",
    }
    overall = "healthy"
    try:
        if service is None:
            raise RuntimeError("service unavailable")
        checks = service.health_check()
        services["database"] = "ok" if checks.get("database") else "offline"
        services["vector_store"] = "ok" if checks.get("retriever") else "offline"
    except Exception:
        services["llm_provider"] = "offline"
        overall = "degraded"

    if "offline" in services.values() and overall == "healthy":
        overall = "degraded"

    return HealthResponse(status=overall, timestamp=datetime.utcnow(), services=services)


@app.post("/api/auth/login", response_model=LoginResponse, tags=["Authentication"])
def login(payload: LoginRequest) -> LoginResponse:
    users = _dev_users()
    user = users.get(payload.email)
    if user is None or not compare_digest(payload.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if payload.role != user["role"]:
        raise HTTPException(status_code=403, detail="Role mismatch for user")

    access_token = _create_token(user, get_settings().access_token_expire_minutes)
    refresh_token = _create_token(user, get_settings().access_token_expire_minutes * 7)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=User(
            user_id=user["user_id"],
            email=user["email"],
            role=user["role"],
            name=user["name"],
            student_id=user.get("student_id"),
            cohort_id=None,
        ),
    )


@app.post("/api/auth/refresh", response_model=LoginResponse, tags=["Authentication"])
def refresh_token(payload: RefreshRequest) -> LoginResponse:
    try:
        token_data = _decode_token(payload.refresh_token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    users = _dev_users()
    user = users.get(token_data.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")

    access_token = _create_token(user, get_settings().access_token_expire_minutes)
    new_refresh_token = _create_token(user, get_settings().access_token_expire_minutes * 7)
    return LoginResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=User(
            user_id=user["user_id"],
            email=user["email"],
            role=user["role"],
            name=user["name"],
            student_id=user.get("student_id"),
            cohort_id=None,
        ),
    )


@app.post("/api/auth/logout", response_model=LogoutResponse, tags=["Authentication"])
def logout(_: TokenData = Depends(get_current_user)) -> LogoutResponse:
    return LogoutResponse()


@app.post("/api/tutor/question", response_model=TutorQuestionResponse, tags=["Tutor"])
def tutor_question(
    payload: TutorQuestionRequest,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    student_db: StudentDB = Depends(get_student_db),
) -> TutorQuestionResponse:
    profile = student_db.get_student_profile(payload.student_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Student not found: {payload.student_id}")

    context = payload.context or {}
    top_k = int(context.get("top_k", TOP_K))
    response = service.answer_question(
        question=payload.question,
        student_id=payload.student_id,
        student_profile=profile,
        top_k=max(top_k, 1),
        conversation_id=payload.conversation_id,
    )
    return response.to_question_model()


@app.post("/api/tutor/answer", response_model=TutorAnswerResponse, tags=["Tutor"])
def tutor_answer(
    payload: TutorAnswerRequest,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    student_db: StudentDB = Depends(get_student_db),
) -> TutorAnswerResponse:
    profile = student_db.get_student_profile(payload.student_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Student not found: {payload.student_id}")

    history = service.get_conversation_by_id(payload.conversation_id, payload.student_id)
    question, hint = _find_question_context(history, payload.turn_id)
    if not question:
        raise HTTPException(status_code=404, detail="Could not resolve source question for evaluation")

    result = service.evaluate_student_answer(
        question=question,
        student_answer=payload.student_answer,
        student_id=payload.student_id,
        student_profile=profile,
        check_answer_hint=payload.check_answer_hint or hint,
        top_k=TOP_K,
        conversation_id=payload.conversation_id,
        turn_id=payload.turn_id,
    )

    ev = result.evaluation_result or {}
    return TutorAnswerResponse(
        conversation_id=result.conversation_id,
        turn_id=result.turn_id,
        is_correct=bool(ev.get("is_correct")),
        feedback=str(ev.get("feedback") or result.answer),
        misconception=ev.get("misconception"),
        confidence=float(ev.get("confidence") or 0.0),
        mastery_event_id=str((result.mastery_event or {}).get("id") or ""),
        remediation=result.remediation_explanation,
        status="evaluated",
        generated_at=result.generated_at,
    )


@app.get(
    "/api/conversations/{student_id}",
    response_model=ConversationResponse,
    tags=["Conversations"],
)
def get_conversation_history(
    student_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> ConversationResponse:
    return service.get_conversation_history(student_id=student_id, limit=limit)


@app.get(
    "/api/conversations/{student_id}/{conversation_id}",
    response_model=ConversationResponse,
    tags=["Conversations"],
)
def get_conversation_by_id(
    student_id: str,
    conversation_id: str,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> ConversationResponse:
    return service.get_conversation_by_id(conversation_id=conversation_id, student_id=student_id)


@app.delete("/api/conversations/{conversation_id}", tags=["Conversations"])
def clear_conversation(
    conversation_id: str,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, bool]:
    return {"deleted": service.clear_conversation_history(conversation_id)}


@app.get("/api/students/{student_id}", response_model=StudentProfile, tags=["Students"])
def get_student(
    student_id: str,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> StudentProfile:
    profile = student_db.get_student_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_id}")
    return _map_student_profile(profile)


@app.put("/api/students/{student_id}", response_model=StudentProfile, tags=["Students"])
def put_student(
    student_id: str,
    payload: StudentProfileRequest,
    _: TokenData = Depends(require_roles("teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> StudentProfile:
    student_db.upsert_student(
        student_id=student_id,
        name=payload.name,
        learning_style=payload.learning_style,
        reading_age=payload.reading_age,
        interest_graph=payload.interests,
        neuro_profile=payload.neuro_profile,
    )
    profile = student_db.get_student_profile(student_id)
    if not profile:
        raise HTTPException(status_code=500, detail="Failed to load saved profile")
    return _map_student_profile(profile)


@app.get(
    "/api/students/{student_id}/mastery",
    response_model=MasteryHistoryResponse,
    tags=["Mastery"],
)
def get_mastery_history(
    student_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    concept_key: str | None = Query(default=None),
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> MasteryHistoryResponse:
    total, events = student_db.get_mastery_events(
        student_id=student_id,
        limit=limit,
        offset=offset,
        concept_key=concept_key,
    )
    mapped = [
        MasteryEvent(
            id=str(item["id"]),
            student_id=item["student_id"],
            concept_key=item["concept_key"],
            is_correct=bool(item["is_correct"]),
            confidence=float(item["confidence"]),
            misconception=item.get("misconception"),
            source_doc=item.get("source_doc") or None,
            source_page=item.get("source_page"),
            source_chunk_id=item.get("source_chunk_id"),
            created_at=_as_dt(item.get("timestamp")),
        )
        for item in events
    ]
    return MasteryHistoryResponse(total=total, events=mapped, limit=limit, offset=offset)


@app.get("/api/students/{student_id}/mastery/stats", tags=["Mastery"])
def get_mastery_stats(
    student_id: str,
    recent_days: int = Query(default=7, ge=1, le=365),
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> dict[str, Any]:
    return student_db.get_mastery_stats(student_id=student_id, recent_days=recent_days)


@app.get("/api/students/{student_id}/goals", response_model=LearningGoalsResponse, tags=["Goals"])
def get_learning_goals(
    student_id: str,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> LearningGoalsResponse:
    rows = student_db.list_learning_goals(student_id)
    active: list[LearningGoal] = []
    archived: list[LearningGoal] = []
    for row in rows:
        goal = LearningGoal(
            goal_id=str(row["id"]),
            goal_text=row["goal_text"],
            is_active=bool(row["is_active"]),
            created_at=_as_dt(row.get("created_at")),
            updated_at=_as_dt(row.get("updated_at")),
        )
        if goal.is_active:
            active.append(goal)
        else:
            archived.append(goal)
    return LearningGoalsResponse(active=active, archived=archived)


@app.post("/api/students/{student_id}/goals", response_model=LearningGoal, tags=["Goals"])
def create_learning_goal(
    student_id: str,
    payload: LearningGoalRequest,
    _: TokenData = Depends(require_roles("teacher", "admin")),
    student_db: StudentDB = Depends(get_student_db),
) -> LearningGoal:
    row = student_db.create_learning_goal(student_id=student_id, goal_text=payload.goal_text)
    return LearningGoal(
        goal_id=str(row["id"]),
        goal_text=row["goal_text"],
        is_active=bool(row["is_active"]),
        created_at=_as_dt(row.get("created_at")),
        updated_at=_as_dt(row.get("updated_at")),
    )


@app.get("/api/admin/retriever/config", response_model=RetrieverConfig, tags=["Admin"])
def get_retriever_config(
    _: TokenData = Depends(require_roles("teacher", "admin")),
    retriever: RAGRetriever = Depends(get_retriever),
) -> RetrieverConfig:
    cfg = retriever.get_config()
    return RetrieverConfig(
        candidate_k=int(cfg["candidate_k"]),
        min_similarity=float(cfg["min_similarity"]),
        dedup_max_per_source_page=int(cfg["dedup_max_per_source_page"]),
        rerank_enabled=bool(cfg["rerank_enabled"]),
        hybrid_enabled=bool(cfg["hybrid_enabled"]),
        top_k=int(cfg["top_k"]),
        notes=f"collection={cfg.get('collection_name')}",
    )


@app.patch("/api/admin/retriever/config", response_model=RetrieverConfig, tags=["Admin"])
def update_retriever_config(
    payload: RetrieverConfig,
    _: TokenData = Depends(require_roles("admin")),
    retriever: RAGRetriever = Depends(get_retriever),
) -> RetrieverConfig:
    updated = retriever.update_config(
        candidate_k=payload.candidate_k,
        min_similarity=payload.min_similarity,
        dedup_max_per_source_page=payload.dedup_max_per_source_page,
        rerank_enabled=payload.rerank_enabled,
        hybrid_enabled=payload.hybrid_enabled,
    )
    return RetrieverConfig(
        candidate_k=int(updated["candidate_k"]),
        min_similarity=float(updated["min_similarity"]),
        dedup_max_per_source_page=int(updated["dedup_max_per_source_page"]),
        rerank_enabled=bool(updated["rerank_enabled"]),
        hybrid_enabled=bool(updated["hybrid_enabled"]),
        top_k=int(updated["top_k"]),
        notes=f"collection={updated.get('collection_name')}",
    )


@app.get("/api/admin/system/stats", tags=["Admin"])
def system_stats(
    _: TokenData = Depends(require_roles("teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, Any]:
    return service.get_stats()


if __name__ == "__main__":
    import uvicorn

    log_level = os.getenv("API_LOG_LEVEL", "info")
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=False, log_level=log_level)