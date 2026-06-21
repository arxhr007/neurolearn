"""FastAPI web application for NeuroLearn (Phase 4)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from hmac import compare_digest
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.conversation import Conversation, Message
from app.models.learning import LearningGoal as LearningGoalModel, MasteryEvent as MasteryEventModel
from app.models.user import Student, Teacher
from app.services.auth import create_access_token, decode_access_token, is_jwt_error
from app.services.learning_service import create_goal
from app.services.user_service import (
    authenticate_admin,
    authenticate_student,
    authenticate_teacher,
    create_student,
    create_teacher,
    ensure_default_admin,
    ensure_single_admin,
    get_student_by_student_id,
    get_teacher_by_id,
    list_students_for_teacher,
    list_teachers,
    update_student,
    update_teacher,
)

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
from langgraph_app.services.sqlalchemy_student_db import SqlAlchemyStudentDB
from langgraph_app.services.tutor_service import TutorService, TutorServiceConfig


logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@asynccontextmanager
async def _lifespan(_: FastAPI):
    from app.database import init_db

    init_db()
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_single_admin(db)
    yield


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
    allow_dev_users: bool = True

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


class TeacherCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str = ""


class TeacherUpdateRequest(BaseModel):
    full_name: str | None = None
    password: str | None = None
    is_active: bool | None = None


class TeacherResponse(BaseModel):
    teacher_id: int
    username: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TeacherListResponse(BaseModel):
    total: int
    teachers: list[TeacherResponse]


class StudentCreateRequest(BaseModel):
    student_id: str
    username: str
    password: str
    full_name: str = ""
    age: int = 10
    reading_age: int = 8
    learning_style: str = "general"
    interests: list[str] = []
    neuro_profile: list[str] = ["general"]


class StudentUpdateRequest(BaseModel):
    full_name: str | None = None
    age: int | None = None
    reading_age: int | None = None
    learning_style: str | None = None
    interests: list[str] | None = None
    neuro_profile: list[str] | None = None
    password: str | None = None
    is_active: bool | None = None


class StudentResponse(BaseModel):
    student_id: str
    username: str
    full_name: str
    age: int
    reading_age: int
    learning_style: str
    interests: list[str]
    neuro_profile: list[str]
    is_active: bool
    teacher_id: int
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseModel):
    total: int
    students: list[StudentResponse]


class ConversationListItem(BaseModel):
    conversation_id: str
    student_id: str
    learning_goal: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationMessageItem(BaseModel):
    message_id: int
    role: str
    message_type: str
    content: str
    payload: dict[str, Any] = {}
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    student_id: str
    learning_goal: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageItem]


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


def _build_login_response(
    *,
    user_id: int,
    username: str,
    role: str,
    name: str,
    student_id: str | None = None,
) -> LoginResponse:
    settings = get_settings()
    access_token = create_access_token(
        username=username,
        role=role,
        user_id=int(user_id),
        student_id=student_id,
        expires_minutes=settings.access_token_expire_minutes,
    )
    refresh_token = create_access_token(
        username=username,
        role=role,
        user_id=int(user_id),
        student_id=student_id,
        expires_minutes=settings.access_token_expire_minutes * 7,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=User(
            user_id=str(user_id),
            email=username,
            role=role,
            name=name,
            student_id=student_id,
            cohort_id=None,
        ),
    )


def _authenticate_db_user(db: Session, payload: LoginRequest) -> LoginResponse | None:
    role = payload.role
    identifier = payload.email
    if role == "admin":
        admin = authenticate_admin(db, identifier, payload.password)
        if admin:
            return _build_login_response(
                user_id=admin.id,
                username=admin.username,
                role="admin",
                name=admin.username,
            )
    if role == "teacher":
        teacher = authenticate_teacher(db, identifier, payload.password)
        if teacher:
            return _build_login_response(
                user_id=teacher.id,
                username=teacher.username,
                role="teacher",
                name=teacher.full_name or teacher.username,
            )
    if role == "student":
        student = authenticate_student(db, identifier, payload.password)
        if student:
            return _build_login_response(
                user_id=student.id,
                username=student.username,
                role="student",
                name=student.full_name or student.username,
                student_id=student.student_id,
            )
    return None


@lru_cache(maxsize=1)
def _service_bundle() -> tuple[TutorService, SqlAlchemyStudentDB, RAGRetriever]:
    _load_runtime_env()
    settings = get_settings()
    if not os.getenv("GROQ_API_KEY") and settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
    if not os.getenv("gemini_api_key") and settings.gemini_api_key:
        os.environ["gemini_api_key"] = settings.gemini_api_key

    student_db = SqlAlchemyStudentDB(SessionLocal)
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
    except SystemExit:
        logger.warning("Tutor service unavailable: missing GROQ_API_KEY")
        return None
    except Exception:
        return None


def get_student_db() -> SqlAlchemyStudentDB:
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
    payload = decode_access_token(token)
    email = payload.get("email") or payload.get("username") or payload.get("sub") or ""
    user_id = payload.get("user_id") or payload.get("sub") or ""
    return TokenData(
        user_id=str(user_id),
        email=str(email),
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
    except Exception as exc:
        if is_jwt_error(exc):
            raise creds_exception from exc
        raise

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


def _map_student_row(student: Student) -> StudentResponse:
    return StudentResponse(
        student_id=student.student_id,
        username=student.username,
        full_name=student.full_name or "",
        age=int(student.age),
        reading_age=int(student.reading_age),
        learning_style=student.learning_style,
        interests=list(student.interests or []),
        neuro_profile=list(student.neuro_profile or []),
        is_active=bool(student.is_active),
        teacher_id=int(student.teacher_id),
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


def _map_teacher_row(teacher: Teacher) -> TeacherResponse:
    return TeacherResponse(
        teacher_id=int(teacher.id),
        username=teacher.username,
        full_name=teacher.full_name or "",
        is_active=bool(teacher.is_active),
        created_at=teacher.created_at,
        updated_at=teacher.updated_at,
    )


def _source_to_dict(source: Any) -> dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump()
    if hasattr(source, "dict"):
        return source.dict()
    return dict(source)


def _as_int_user_id(user: TokenData) -> int:
    try:
        return int(user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Unsupported auth context for this action") from exc


def _require_student_access(db: Session, user: TokenData, student_id: str) -> Student:
    student = get_student_by_student_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if user.role == "student":
        if user.student_id != student.student_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    elif user.role == "teacher":
        teacher_id = _as_int_user_id(user)
        if int(student.teacher_id) != int(teacher_id):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return student


def _get_active_goal_text(db: Session, student_pk: int) -> str | None:
    goal = (
        db.query(LearningGoalModel)
        .filter(LearningGoalModel.student_id == student_pk, LearningGoalModel.is_active.is_(True))
        .order_by(LearningGoalModel.updated_at.desc())
        .first()
    )
    return goal.goal_text if goal else None


def _get_or_create_conversation(
    db: Session,
    *,
    student_pk: int,
    conversation_id: str,
    learning_goal: str | None,
) -> Conversation:
    convo = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not convo:
        convo = Conversation(
            conversation_id=conversation_id,
            student_id=student_pk,
            learning_goal=learning_goal,
        )
        db.add(convo)
        db.flush()
        db.refresh(convo)
    if learning_goal and convo.learning_goal != learning_goal:
        convo.learning_goal = learning_goal
        db.add(convo)
    return convo


def _save_message(
    db: Session,
    *,
    conversation: Conversation,
    role: str,
    message_type: str,
    content: str,
    payload: dict[str, Any] | None = None,
    turn_id: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation.id,
        role=role,
        message_type=message_type,
        content=content,
        payload=payload or {},
        turn_id=turn_id,
    )
    db.add(msg)
    return msg


def _persist_question_turn(
    db: Session,
    *,
    student_pk: int,
    conversation_id: str,
    question: str,
    response: Any,
) -> None:
    learning_goal = _get_active_goal_text(db, student_pk)
    convo = _get_or_create_conversation(
        db,
        student_pk=student_pk,
        conversation_id=conversation_id,
        learning_goal=learning_goal,
    )
    _save_message(
        db,
        conversation=convo,
        role="student",
        message_type="question",
        content=question,
        payload={"turn_id": response.turn_id},
        turn_id=response.turn_id,
    )
    _save_message(
        db,
        conversation=convo,
        role="assistant",
        message_type="answer",
        content=response.answer or "",
        payload={
            "turn_id": response.turn_id,
            "sources": [_source_to_dict(s) for s in (response.sources or [])],
        },
        turn_id=response.turn_id,
    )
    if response.check_question:
        _save_message(
            db,
            conversation=convo,
            role="assistant",
            message_type="check_question",
            content=response.check_question,
            payload={
                "turn_id": response.turn_id,
                "check_answer_hint": response.check_answer_hint,
            },
            turn_id=response.turn_id,
        )
    convo.updated_at = datetime.utcnow()
    db.add(convo)


def _persist_answer_turn(
    db: Session,
    *,
    student_pk: int,
    conversation_id: str,
    student_answer: str,
    response: Any,
) -> None:
    learning_goal = _get_active_goal_text(db, student_pk)
    convo = _get_or_create_conversation(
        db,
        student_pk=student_pk,
        conversation_id=conversation_id,
        learning_goal=learning_goal,
    )
    _save_message(
        db,
        conversation=convo,
        role="student",
        message_type="answer",
        content=student_answer,
        payload={"turn_id": response.turn_id},
        turn_id=response.turn_id,
    )
    _save_message(
        db,
        conversation=convo,
        role="assistant",
        message_type="evaluation",
        content=response.answer or "",
        payload={
            "turn_id": response.turn_id,
            "evaluation_result": response.evaluation_result or {},
        },
        turn_id=response.turn_id,
    )
    if response.remediation_explanation:
        _save_message(
            db,
            conversation=convo,
            role="assistant",
            message_type="remediation",
            content=response.remediation_explanation,
            payload={"turn_id": response.turn_id},
            turn_id=response.turn_id,
        )
    convo.updated_at = datetime.utcnow()
    db.add(convo)


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
    lifespan=_lifespan,
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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    response = _authenticate_db_user(db, payload)
    if response:
        return response

    settings = get_settings()
    if settings.allow_dev_users:
        users = _dev_users()
        user = users.get(payload.email)
        if user is None or not compare_digest(payload.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if payload.role != user["role"]:
            raise HTTPException(status_code=403, detail="Role mismatch for user")
        return _build_login_response(
            user_id=0,
            username=user["email"],
            role=user["role"],
            name=user["name"],
            student_id=user.get("student_id"),
        )

    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/auth/refresh", response_model=LoginResponse, tags=["Authentication"])
def refresh_token(payload: RefreshRequest) -> LoginResponse:
    try:
        token_data = _decode_token(payload.refresh_token)
    except Exception as exc:
        if is_jwt_error(exc):
            raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
        raise

    try:
        user_id = int(token_data.user_id)
    except Exception:
        user_id = 0

    return _build_login_response(
        user_id=user_id,
        username=token_data.email,
        role=token_data.role,
        name=token_data.email,
        student_id=token_data.student_id,
    )


@app.post("/api/auth/logout", response_model=LogoutResponse, tags=["Authentication"])
def logout(_: TokenData = Depends(get_current_user)) -> LogoutResponse:
    return LogoutResponse()


@app.post("/api/tutor/question", response_model=TutorQuestionResponse, tags=["Tutor"])
def tutor_question(
    payload: TutorQuestionRequest,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> TutorQuestionResponse:
    student = _require_student_access(db, current_user, payload.student_id)
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
    _persist_question_turn(
        db,
        student_pk=int(student.id),
        conversation_id=payload.conversation_id,
        question=payload.question,
        response=response,
    )
    return response.to_question_model()


@app.post("/api/tutor/answer", response_model=TutorAnswerResponse, tags=["Tutor"])
def tutor_answer(
    payload: TutorAnswerRequest,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> TutorAnswerResponse:
    student = _require_student_access(db, current_user, payload.student_id)
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
    _persist_answer_turn(
        db,
        student_pk=int(student.id),
        conversation_id=payload.conversation_id,
        student_answer=payload.student_answer,
        response=result,
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
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    _require_student_access(db, current_user, student_id)
    return service.get_conversation_history(student_id=student_id, limit=limit)


@app.get(
    "/api/conversations/{student_id}/{conversation_id}",
    response_model=ConversationResponse,
    tags=["Conversations"],
)
def get_conversation_by_id(
    student_id: str,
    conversation_id: str,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    _require_student_access(db, current_user, student_id)
    return service.get_conversation_by_id(conversation_id=conversation_id, student_id=student_id)


@app.get(
    "/api/conversations/{student_id}/{conversation_id}/{turn_id}/story",
    tags=["Tutor"],
)
def get_conversation_turn_story(
    student_id: str,
    conversation_id: str,
    turn_id: str,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Return a storyified variant of the answer for the requested conversation turn.

    This endpoint reconstructs a minimal `state` from the stored conversation turn
    and delegates to `TutorService.generate_story_from_state`. It is intentionally
    a read-only, opt-in helper.
    """
    _require_student_access(db, current_user, student_id)
    profile = student_db.get_student_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_id}")

    conversation = service.get_conversation_by_id(conversation_id=conversation_id, student_id=student_id)
    # Find the requested turn
    target = None
    for t in conversation.turns:
        if t.turn_id == turn_id:
            target = t
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Turn not found")

    answer_text = target.answer or ""
    question_text = target.question or ""
    docs = []
    for s in (target.sources or []):
        # convert Source pydantic model to minimal doc dict
        try:
            docs.append({"source": s.source, "page": s.page, "text": s.excerpt})
        except Exception:
            # fallback for plain dict-like values
            docs.append({"source": getattr(s, "source", ""), "page": getattr(s, "page", None), "text": getattr(s, "excerpt", "")})

    if not answer_text:
        raise HTTPException(status_code=400, detail="No answer text available for this turn")

    state = {"answer": answer_text, "question": question_text, "docs": docs}

    try:
        story = service.generate_story_from_state(state, student_id=student_id, student_profile=profile)
    except Exception as exc:
        logger.exception("Failed to generate story for turn")
        raise HTTPException(status_code=500, detail=f"Story generation failed: {exc}") from exc

    return {"conversation_id": conversation_id, "turn_id": turn_id, "story": story}


@app.get("/api/chapters", tags=["Tutor"])
def list_chapters(
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, Any]:
    del current_user
    return {"chapters": service.list_available_chapters()}


class ChapterLearnRequest(BaseModel):
    source: str
    module_number: int | None = None


@app.get("/api/chapters/{source}/modules", tags=["Tutor"])
def list_chapter_modules(
    source: str,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, Any]:
    del current_user
    modules = service.get_chapter_modules(source)
    return {"modules": modules, "source": source}


@app.post("/api/chapters/learn", tags=["Tutor"])
def chapter_learn(
    req: ChapterLearnRequest,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, Any]:
    student_id = current_user.student_id
    module = None
    if req.module_number:
        modules = service.get_chapter_modules(req.source)
        for m in modules:
            if m["number"] == req.module_number:
                module = m
                break
        chapter_docs = service.load_module_docs(req.source, req.module_number)
    else:
        chapter_docs = service.load_chapter_docs(req.source)

    if not chapter_docs:
        raise HTTPException(status_code=404, detail="No content found for this chapter/module")

    topic = module["title"] if module else req.source

    from langgraph_app.services.chapter_mode import plan_chapter_session
    session_plan = plan_chapter_session(topic, chapter_docs)
    question_count = session_plan.get("question_count", 3)

    combined_text = "\n\n".join(str(d.get("text") or "") for d in chapter_docs if d)
    student_profile = None
    try:
        student_profile = service.student_db.get_student_profile(student_id)
    except Exception:
        pass

    story = ""
    try:
        story = service.llm.generate_story_from_answer(
            answer=combined_text or topic,
            question=f"{req.source} | Module {req.module_number}" if req.module_number else req.source,
            context_docs=chapter_docs[:3],
            student_profile=student_profile,
            max_tokens=4096,
        )
    except Exception:
        logger.exception("Failed to generate story for chapter learn")

    questions = []
    for qi in range(1, question_count + 1):
        try:
            bundle = service.generate_chapter_drill_bundle(
                chapter_name=req.source,
                topic=topic,
                chapter_docs=chapter_docs,
                student_profile=student_profile,
                question_index=qi,
                total_questions=question_count,
                previous_questions=[q["question"] for q in questions],
            )
            questions.append({
                "question": bundle.get("question", ""),
                "expected_answer": bundle.get("expected_answer", ""),
            })
        except Exception:
            logger.exception(f"Failed to generate drill question {qi}")
            break

    return {
        "story": story,
        "questions": questions,
        "session_plan": session_plan,
        "module": module,
        "topic": topic,
    }


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
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> StudentProfile:
    _require_student_access(db, current_user, student_id)
    profile = student_db.get_student_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_id}")
    return _map_student_profile(profile)


@app.put("/api/students/{student_id}", response_model=StudentProfile, tags=["Students"])
def put_student(
    student_id: str,
    payload: StudentProfileRequest,
    current_user: TokenData = Depends(require_roles("teacher", "admin")),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> StudentProfile:
    _require_student_access(db, current_user, student_id)
    update_student(
        db,
        student_id=student_id,
        full_name=payload.name,
        reading_age=payload.reading_age,
        learning_style=payload.learning_style,
        interests=payload.interests,
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
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> MasteryHistoryResponse:
    _require_student_access(db, current_user, student_id)
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
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_student_access(db, current_user, student_id)
    return student_db.get_mastery_stats(student_id=student_id, recent_days=recent_days)


@app.get("/api/students/{student_id}/goals", response_model=LearningGoalsResponse, tags=["Goals"])
def get_learning_goals(
    student_id: str,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    db: Session = Depends(get_db),
) -> LearningGoalsResponse:
    student = _require_student_access(db, current_user, student_id)
    rows = (
        db.query(LearningGoalModel)
        .filter(LearningGoalModel.student_id == student.id)
        .order_by(LearningGoalModel.updated_at.desc())
        .all()
    )
    active: list[LearningGoal] = []
    archived: list[LearningGoal] = []
    for row in rows:
        goal = LearningGoal(
            goal_id=str(row.id),
            goal_text=row.goal_text,
            is_active=bool(row.is_active),
            created_at=_as_dt(row.created_at),
            updated_at=_as_dt(row.updated_at),
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
    current_user: TokenData = Depends(require_roles("teacher", "admin")),
    db: Session = Depends(get_db),
) -> LearningGoal:
    student = _require_student_access(db, current_user, student_id)
    row = create_goal(db, student_id=student.id, goal_text=payload.goal_text)
    return LearningGoal(
        goal_id=str(row.id),
        goal_text=row.goal_text,
        is_active=bool(row.is_active),
        created_at=_as_dt(row.created_at),
        updated_at=_as_dt(row.updated_at),
    )


@app.get("/api/admin/teachers", response_model=TeacherListResponse, tags=["Admin"])
def list_admin_teachers(
    _: TokenData = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> TeacherListResponse:
    teachers = list_teachers(db)
    return TeacherListResponse(
        total=len(teachers),
        teachers=[_map_teacher_row(teacher) for teacher in teachers],
    )


@app.post("/api/admin/teachers", response_model=TeacherResponse, tags=["Admin"])
def create_admin_teacher(
    payload: TeacherCreateRequest,
    _: TokenData = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    teacher = create_teacher(db, username=payload.username, password=payload.password, full_name=payload.full_name)
    return _map_teacher_row(teacher)


@app.get("/api/admin/teachers/{teacher_id}", response_model=TeacherResponse, tags=["Admin"])
def get_admin_teacher(
    teacher_id: int,
    _: TokenData = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    teacher = get_teacher_by_id(db, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return _map_teacher_row(teacher)


@app.put("/api/admin/teachers/{teacher_id}", response_model=TeacherResponse, tags=["Admin"])
def update_admin_teacher(
    teacher_id: int,
    payload: TeacherUpdateRequest,
    _: TokenData = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    teacher = update_teacher(
        db,
        teacher_id,
        full_name=payload.full_name,
        password=payload.password,
        is_active=payload.is_active,
    )
    return _map_teacher_row(teacher)


@app.get("/api/teacher/students", response_model=StudentListResponse, tags=["Teacher"])
def list_teacher_students(
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> StudentListResponse:
    teacher_id = _as_int_user_id(current_user)
    students = list_students_for_teacher(db, teacher_id)
    return StudentListResponse(
        total=len(students),
        students=[_map_student_row(student) for student in students],
    )


@app.post("/api/teacher/students", response_model=StudentResponse, tags=["Teacher"])
def create_teacher_student(
    payload: StudentCreateRequest,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> StudentResponse:
    teacher_id = _as_int_user_id(current_user)
    student = create_student(
        db,
        teacher_id=teacher_id,
        student_id=payload.student_id,
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        age=payload.age,
        reading_age=payload.reading_age,
        learning_style=payload.learning_style,
        interests=payload.interests,
        neuro_profile=payload.neuro_profile,
    )
    return _map_student_row(student)


@app.get("/api/teacher/students/{student_id}", response_model=StudentResponse, tags=["Teacher"])
def get_teacher_student(
    student_id: str,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> StudentResponse:
    student = _require_student_access(db, current_user, student_id)
    return _map_student_row(student)


@app.put("/api/teacher/students/{student_id}", response_model=StudentResponse, tags=["Teacher"])
def update_teacher_student(
    student_id: str,
    payload: StudentUpdateRequest,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> StudentResponse:
    _require_student_access(db, current_user, student_id)
    student = update_student(
        db,
        student_id=student_id,
        full_name=payload.full_name,
        age=payload.age,
        reading_age=payload.reading_age,
        learning_style=payload.learning_style,
        interests=payload.interests,
        neuro_profile=payload.neuro_profile,
        password=payload.password,
        is_active=payload.is_active,
    )
    return _map_student_row(student)


@app.get("/api/teacher/students/{student_id}/goals", response_model=LearningGoalsResponse, tags=["Teacher"])
def list_teacher_student_goals(
    student_id: str,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> LearningGoalsResponse:
    student = _require_student_access(db, current_user, student_id)
    goals = (
        db.query(LearningGoalModel)
        .filter(LearningGoalModel.student_id == student.id)
        .order_by(LearningGoalModel.updated_at.desc())
        .all()
    )
    active: list[LearningGoal] = []
    archived: list[LearningGoal] = []
    for goal_row in goals:
        goal = LearningGoal(
            goal_id=str(goal_row.id),
            goal_text=goal_row.goal_text,
            is_active=bool(goal_row.is_active),
            created_at=_as_dt(goal_row.created_at),
            updated_at=_as_dt(goal_row.updated_at),
        )
        if goal.is_active:
            active.append(goal)
        else:
            archived.append(goal)
    return LearningGoalsResponse(active=active, archived=archived)


@app.post("/api/teacher/students/{student_id}/goals", response_model=LearningGoal, tags=["Teacher"])
def create_teacher_student_goal(
    student_id: str,
    payload: LearningGoalRequest,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> LearningGoal:
    student = _require_student_access(db, current_user, student_id)
    goal = create_goal(db, student_id=student.id, goal_text=payload.goal_text)
    return LearningGoal(
        goal_id=str(goal.id),
        goal_text=goal.goal_text,
        is_active=bool(goal.is_active),
        created_at=_as_dt(goal.created_at),
        updated_at=_as_dt(goal.updated_at),
    )


@app.get("/api/teacher/students/{student_id}/mastery", response_model=MasteryHistoryResponse, tags=["Teacher"])
def list_teacher_student_mastery(
    student_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    concept_key: str | None = Query(default=None),
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
) -> MasteryHistoryResponse:
    _require_student_access(db, current_user, student_id)
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


@app.get("/api/teacher/students/{student_id}/mastery/stats", tags=["Teacher"])
def teacher_student_mastery_stats(
    student_id: str,
    recent_days: int = Query(default=7, ge=1, le=365),
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
    student_db: SqlAlchemyStudentDB = Depends(get_student_db),
) -> dict[str, Any]:
    _require_student_access(db, current_user, student_id)
    return student_db.get_mastery_stats(student_id=student_id, recent_days=recent_days)


@app.get("/api/teacher/students/{student_id}/conversations", response_model=list[ConversationListItem], tags=["Teacher"])
def list_teacher_student_conversations(
    student_id: str,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> list[ConversationListItem]:
    student = _require_student_access(db, current_user, student_id)
    conversations = (
        db.query(Conversation)
        .filter(Conversation.student_id == student.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        ConversationListItem(
            conversation_id=conv.conversation_id,
            student_id=student.student_id,
            learning_goal=conv.learning_goal,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]


@app.get(
    "/api/teacher/students/{student_id}/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    tags=["Teacher"],
)
def get_teacher_student_conversation(
    student_id: str,
    conversation_id: str,
    current_user: TokenData = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    student = _require_student_access(db, current_user, student_id)
    convo = (
        db.query(Conversation)
        .filter(Conversation.student_id == student.id, Conversation.conversation_id == conversation_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == convo.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ConversationDetailResponse(
        conversation_id=convo.conversation_id,
        student_id=student.student_id,
        learning_goal=convo.learning_goal,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
        messages=[
            ConversationMessageItem(
                message_id=int(msg.id),
                role=msg.role,
                message_type=msg.message_type,
                content=msg.content,
                payload=msg.payload or {},
                created_at=msg.created_at,
            )
            for msg in messages
        ],
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


STORY_JSON_DIR = Path(__file__).parent / "input" / "story"


@app.get("/api/story/curricula", tags=["Story"])
def list_story_curricula(
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
) -> dict[str, Any]:
    """List available story curriculum JSON files."""
    curricula = []
    for f in sorted(STORY_JSON_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            curricula.append({
                "name": f.stem,
                "title": data.get("curriculum_title", f.stem),
                "module_count": len(data.get("modules", [])),
            })
        except Exception:
            logger.warning("Failed to parse story curriculum %s", f.name)
    return {"curricula": curricula}


@app.get("/api/story/curricula/{name}", tags=["Story"])
def get_story_curriculum(
    name: str,
    _: TokenData = Depends(require_roles("student", "teacher", "admin")),
) -> dict[str, Any]:
    """Get full curriculum data with modules and activities."""
    path = STORY_JSON_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Curriculum '{name}' not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse curriculum: {exc}")


class StoryGenerateRequest(BaseModel):
    curriculum: str
    module_number: int
    activity_id: str
    placeholder_values: dict[str, str] = {}


class TTSRequest(BaseModel):
    text: str
    voice: str = "ml-IN-SobhanaNeural"
    speaking_rate: float = 0.9


@app.post("/api/story/tts", tags=["Story"])
def story_tts(req: TTSRequest):
    """Generate TTS audio using edge-tts (free, no API key needed)."""
    try:
        import edge_tts
        import base64
        import io
        import asyncio

        voice = req.voice if req.voice and req.voice.startswith("ml") else "ml-IN-SobhanaNeural"
        async def _gen():
            communicate = edge_tts.Communicate(req.text, voice)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")

        audio_b64 = asyncio.run(_gen())
        return {"audioContent": audio_b64}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TTS failed: {exc}")


@app.post("/api/story/generate", tags=["Story"])
def generate_story_from_template(
    req: StoryGenerateRequest,
    current_user: TokenData = Depends(require_roles("student", "teacher", "admin")),
    service: TutorService = Depends(get_tutor_service),
) -> dict[str, Any]:
    """Generate a story from a curriculum template with filled placeholders."""
    path = STORY_JSON_DIR / f"{req.curriculum}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Curriculum '{req.curriculum}' not found")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse curriculum: {exc}")

    module = None
    activity = None
    for m in data.get("modules", []):
        if m.get("module_number") == req.module_number:
            module = m
            for a in m.get("activities", []):
                if a.get("activity_id") == req.activity_id:
                    activity = a
                    break
            break

    if not activity:
        raise HTTPException(
            status_code=404,
            detail=f"Activity '{req.activity_id}' not found in module {req.module_number}",
        )

    template = activity.get("story_template_malayalam", "")
    if not template:
        raise HTTPException(status_code=400, detail="Activity has no story template")

    # Fill placeholders
    filled_template = template
    for key, value in req.placeholder_values.items():
        filled_template = filled_template.replace("{" + key + "}", value)

    # Build context from activity metadata
    context_docs = [
        {"source": data.get("curriculum_title", ""), "page": 0, "text": f"Theme: {activity.get('story_theme', '')}"},
        {"source": data.get("curriculum_title", ""), "page": 0, "text": f"Concept: {activity.get('main_concept', '')}"},
        {"source": data.get("curriculum_title", ""), "page": 0, "text": f"Challenge: {'; '.join(activity.get('possible_challenges', [])[:3])}"},
    ]

    student_id = current_user.student_id
    student_profile = None
    try:
        student_profile = service.student_db.get_student_profile(student_id)
    except Exception:
        pass

    story = ""
    try:
        story = service.llm.generate_story_from_answer(
            answer=filled_template,
            question=f"{activity.get('activity_name', '')} – {module.get('module_title', '')}",
            context_docs=context_docs,
            student_profile=student_profile,
            max_tokens=16384,
        )
    except Exception:
        logger.exception("Failed to generate story from template")

    return {
        "story": story,
        "activity": {
            "id": activity.get("activity_id"),
            "name": activity.get("activity_name"),
            "theme": activity.get("story_theme"),
            "moral": activity.get("moral"),
        },
        "module_title": module.get("module_title") if module else "",
        "curriculum_title": data.get("curriculum_title", ""),
    }


if __name__ == "__main__":
    import uvicorn

    log_level = os.getenv("API_LOG_LEVEL", "info")
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=False, log_level=log_level)