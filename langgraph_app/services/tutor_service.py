"""Service layer for tutoring orchestration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from langgraph_app.graph.builder import invoke_graph_safe
from langgraph_app.models import (
    ConversationResponse,
    ConversationTurn,
    Source,
    TutorQuestionResponse,
)
from langgraph_app.services.retriever_base import RetrieverBase
from langgraph_app.services.student_db_base import StudentDBBase


@dataclass
class TutorServiceConfig:
    """Configuration for TutorService behavior."""

    default_top_k_retrieval: int = 5
    default_response_timeout_seconds: int = 30
    enable_conversation_history: bool = True


@dataclass
class TutorResponse:
    """Normalized response returned by TutorService."""

    conversation_id: str
    turn_id: str
    status: str
    answer: str = ""
    check_question: Optional[str] = None
    check_answer_hint: Optional[str] = None
    sources: list[Source] = field(default_factory=list)
    evaluation_result: dict[str, Any] = field(default_factory=dict)
    mastery_event: dict[str, Any] | None = None
    remediation_explanation: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)
    raw_state: dict[str, Any] = field(default_factory=dict)

    def is_waiting_for_answer(self) -> bool:
        return self.status == "waiting_for_answer"

    def is_evaluated(self) -> bool:
        return self.status == "evaluated"

    def is_error(self) -> bool:
        return self.status == "error"

    def is_success(self) -> bool:
        return self.status in {"answered", "waiting_for_answer", "evaluated"}

    def to_question_model(self) -> TutorQuestionResponse:
        return TutorQuestionResponse(
            conversation_id=self.conversation_id,
            turn_id=self.turn_id,
            answer=self.answer,
            check_question=self.check_question,
            check_answer_hint=self.check_answer_hint,
            sources=self.sources,
            status=self.status,
            generated_at=self.generated_at,
        )


class TutorService:
    """Encapsulates tutoring graph execution and lightweight conversation state."""

    def __init__(
        self,
        graph: Any,
        retriever: RetrieverBase,
        student_db: StudentDBBase,
        llm: Any,
        config: Optional[TutorServiceConfig] = None,
    ) -> None:
        if graph is None:
            raise ValueError("graph cannot be None")
        if retriever is None:
            raise ValueError("retriever cannot be None")
        if student_db is None:
            raise ValueError("student_db cannot be None")
        if llm is None:
            raise ValueError("llm cannot be None")

        self.graph = graph
        self.retriever = retriever
        self.student_db = student_db
        self.llm = llm
        self.config = config or TutorServiceConfig()
        self._history: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def ask_question(
        self,
        question: str,
        student_id: str,
        student_profile: dict[str, Any] | None = None,
        top_k: int | None = None,
        conversation_id: str | None = None,
    ) -> TutorResponse:
        """Run the graph for a student question turn."""
        conversation_id = conversation_id or str(uuid4())
        turn_id = str(uuid4())
        profile = self._resolve_student_profile(student_id, student_profile)
        payload = self._build_payload(
            question=question,
            student_id=student_id,
            student_profile=profile,
            top_k=top_k,
            conversation_id=conversation_id,
        )
        state = self._invoke(payload)
        response = self._build_question_response(conversation_id, turn_id, state)
        self._store_turn(
            conversation_id=conversation_id,
            student_id=student_id,
            learning_goal=self._extract_active_goal(student_id),
            turn=self._build_question_turn(turn_id, question, response),
        )
        return response

    def answer_question(
        self,
        question: str,
        student_id: str,
        student_profile: dict[str, Any] | None = None,
        top_k: int | None = None,
        conversation_id: str | None = None,
    ) -> TutorResponse:
        """Alias for ask_question() kept for plan-aligned API naming."""
        return self.ask_question(
            question=question,
            student_id=student_id,
            student_profile=student_profile,
            top_k=top_k,
            conversation_id=conversation_id,
        )

    def evaluate_answer(
        self,
        question: str,
        student_answer: str,
        student_id: str,
        student_profile: dict[str, Any] | None = None,
        check_answer_hint: str | None = None,
        top_k: int | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
    ) -> TutorResponse:
        """Run the graph for an answer-evaluation turn."""
        conversation_id = conversation_id or str(uuid4())
        turn_id = turn_id or str(uuid4())
        profile = self._resolve_student_profile(student_id, student_profile)
        payload = self._build_payload(
            question=question,
            student_id=student_id,
            student_profile=profile,
            top_k=top_k,
            conversation_id=conversation_id,
            student_response=student_answer,
            check_answer_hint=check_answer_hint,
        )
        state = self._invoke(payload)
        response = self._build_answer_response(conversation_id, turn_id, state)
        self._store_turn(
            conversation_id=conversation_id,
            student_id=student_id,
            learning_goal=self._extract_active_goal(student_id),
            turn=self._build_answer_turn(turn_id, question, student_answer, response),
        )
        return response

    def evaluate_student_answer(
        self,
        question: str,
        student_answer: str,
        student_id: str,
        student_profile: dict[str, Any] | None = None,
        check_answer_hint: str | None = None,
        top_k: int | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
    ) -> TutorResponse:
        """Alias for evaluate_answer() kept for plan-aligned API naming."""
        return self.evaluate_answer(
            question=question,
            student_answer=student_answer,
            student_id=student_id,
            student_profile=student_profile,
            check_answer_hint=check_answer_hint,
            top_k=top_k,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )

    def get_conversation_history(self, student_id: str, limit: int = 10) -> ConversationResponse:
        """Return the most recent in-memory conversation history for a student."""
        with self._lock:
            recent: tuple[str, dict[str, Any]] | None = None
            for conversation_id, entry in self._history.items():
                if entry.get("student_id") != student_id:
                    continue
                if recent is None or entry["updated_at"] > recent[1]["updated_at"]:
                    recent = (conversation_id, entry)

            if not recent:
                now = datetime.utcnow()
                return ConversationResponse(
                    conversation_id=str(uuid4()),
                    student_id=student_id,
                    created_at=now,
                    updated_at=now,
                    turns=[],
                    learning_goal=self._extract_active_goal(student_id),
                )

            conversation_id, entry = recent
            turns = list(entry["turns"])[-max(int(limit), 1):]
            return ConversationResponse(
                conversation_id=conversation_id,
                student_id=entry["student_id"],
                created_at=entry["created_at"],
                updated_at=entry["updated_at"],
                turns=turns,
                learning_goal=entry.get("learning_goal"),
            )

    def get_conversation_by_id(self, conversation_id: str, student_id: str) -> ConversationResponse:
        """Return a specific conversation history by conversation id."""
        with self._lock:
            entry = self._history.get(conversation_id)
            if not entry:
                now = datetime.utcnow()
                return ConversationResponse(
                    conversation_id=conversation_id,
                    student_id=student_id,
                    created_at=now,
                    updated_at=now,
                    turns=[],
                    learning_goal=self._extract_active_goal(student_id),
                )
            return ConversationResponse(
                conversation_id=conversation_id,
                student_id=entry["student_id"],
                created_at=entry["created_at"],
                updated_at=entry["updated_at"],
                turns=list(entry["turns"]),
                learning_goal=entry.get("learning_goal"),
            )

    def clear_conversation_history(self, conversation_id: str) -> bool:
        with self._lock:
            return self._history.pop(conversation_id, None) is not None

    def get_mastery_stats(self, student_id: str) -> dict[str, Any]:
        return self.student_db.get_mastery_stats(student_id)

    def get_learning_goals(self, student_id: str) -> list[dict[str, Any]]:
        return self.student_db.get_learning_goals(student_id)

    def get_active_learning_goal(self, student_id: str) -> Any:
        return self.student_db.get_active_learning_goal(student_id)

    def health_check(self) -> dict[str, bool]:
        return {
            "graph": True,
            "retriever": self.retriever.health_check(),
            "database": self.student_db.health_check(),
        }

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            conversation_count = len(self._history)
        return {
            "conversation_count": conversation_count,
            "retriever": self.retriever.get_stats(),
            "database_healthy": self.student_db.health_check(),
            "health": self.health_check(),
        }

    def _invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        return invoke_graph_safe(
            self.graph,
            payload,
            timeout_seconds=self.config.default_response_timeout_seconds,
        )

    def _resolve_student_profile(
        self,
        student_id: str,
        student_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if student_profile is not None:
            return dict(student_profile)
        profile = self.student_db.get_student_profile(student_id)
        return dict(profile or {})

    def _extract_active_goal(self, student_id: str) -> str | None:
        goal = self.student_db.get_active_learning_goal(student_id)
        if isinstance(goal, dict):
            return goal.get("goal_text") or goal.get("goal")
        return None

    def _build_payload(
        self,
        question: str,
        student_id: str,
        student_profile: dict[str, Any],
        top_k: int | None,
        conversation_id: str,
        student_response: str | None = None,
        check_answer_hint: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "student_id": student_id,
            "student_db": self.student_db,
            "llm": self.llm,
            "question": question,
            "student_response": student_response if student_response is not None else question,
            "top_k": top_k or self.config.default_top_k_retrieval,
            "student_profile": student_profile,
            "conversation_id": conversation_id,
        }
        if check_answer_hint:
            payload["check_answer_hint"] = check_answer_hint
        return payload

    def _format_source(self, doc: dict[str, Any]) -> Source:
        source_name = str(doc.get("source") or "unknown")
        page_value = doc.get("page")
        chunk_value = doc.get("chunk_id")
        excerpt = str(doc.get("text") or doc.get("content") or "").strip()
        return Source(
            source=source_name,
            page=int(page_value) if page_value is not None else 0,
            chunk_id=str(chunk_value) if chunk_value is not None else "",
            excerpt=excerpt,
            distance=doc.get("distance"),
            similarity_score=doc.get("similarity_score") or doc.get("blended_score"),
        )

    def _build_sources(self, state: dict[str, Any]) -> list[Source]:
        return [self._format_source(doc) for doc in state.get("docs", []) or []]

    def _build_question_response(
        self,
        conversation_id: str,
        turn_id: str,
        state: dict[str, Any],
    ) -> TutorResponse:
        answer = state.get("answer")
        if answer is None:
            evaluation_result = state.get("evaluation_result") or {}
            answer = evaluation_result.get("feedback") or ""
        check_question = state.get("check_question")
        check_answer_hint = state.get("check_answer_hint")
        sources = self._build_sources(state)
        status = "waiting_for_answer" if check_question else "answered"
        if not answer and not check_question:
            status = "error"
        return TutorResponse(
            conversation_id=conversation_id,
            turn_id=turn_id,
            status=status,
            answer=str(answer or ""),
            check_question=check_question,
            check_answer_hint=check_answer_hint,
            sources=sources,
            evaluation_result=state.get("evaluation_result") or {},
            mastery_event=state.get("mastery_event"),
            remediation_explanation=state.get("remediation_explanation"),
            raw_state=state,
        )

    def _build_answer_response(
        self,
        conversation_id: str,
        turn_id: str,
        state: dict[str, Any],
    ) -> TutorResponse:
        evaluation_result = state.get("evaluation_result") or {}
        return TutorResponse(
            conversation_id=conversation_id,
            turn_id=turn_id,
            status="evaluated",
            answer=str(evaluation_result.get("feedback") or state.get("answer") or ""),
            sources=self._build_sources(state),
            evaluation_result=evaluation_result,
            mastery_event=state.get("mastery_event"),
            remediation_explanation=state.get("remediation_explanation"),
            raw_state=state,
        )

    def _build_question_turn(self, turn_id: str, question: str, response: TutorResponse) -> ConversationTurn:
        return ConversationTurn(
            turn_id=turn_id,
            type="question",
            question=question,
            answer=response.answer,
            check_question=response.check_question,
            check_answer_hint=response.check_answer_hint,
            sources=response.sources,
            generated_at=response.generated_at,
        )

    def _build_answer_turn(
        self,
        turn_id: str,
        question: str,
        student_answer: str,
        response: TutorResponse,
    ) -> ConversationTurn:
        return ConversationTurn(
            turn_id=turn_id,
            type="answer",
            question=question,
            student_answer=student_answer,
            answer=response.answer,
            is_correct=bool((response.evaluation_result or {}).get("is_correct")),
            feedback=(response.evaluation_result or {}).get("feedback"),
            misconception=(response.evaluation_result or {}).get("misconception"),
            confidence=(response.evaluation_result or {}).get("confidence"),
            mastery_event_id=str((response.mastery_event or {}).get("id")) if response.mastery_event else None,
            remediation=response.remediation_explanation,
            generated_at=response.generated_at,
        )

    def _store_turn(
        self,
        conversation_id: str,
        student_id: str,
        learning_goal: str | None,
        turn: ConversationTurn,
    ) -> None:
        if not self.config.enable_conversation_history:
            return
        with self._lock:
            entry = self._history.get(conversation_id)
            if entry is None:
                entry = {
                    "student_id": student_id,
                    "created_at": turn.generated_at,
                    "updated_at": turn.generated_at,
                    "turns": [],
                    "learning_goal": learning_goal,
                }
                self._history[conversation_id] = entry
            entry["turns"].append(turn)
            entry["updated_at"] = turn.generated_at
            if learning_goal and not entry.get("learning_goal"):
                entry["learning_goal"] = learning_goal
