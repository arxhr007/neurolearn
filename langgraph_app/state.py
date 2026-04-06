"""Typed state shared across LangGraph nodes."""

from typing import TypedDict


class RAGState(TypedDict, total=False):
    student_id: str
    student_db: object
    active_learning_goal: str
    drift_detected: bool
    drift_reason: str
    drift_message: str
    force_intent: str
    question: str
    student_response: str
    top_k: int
    student_profile: dict
    intent: str
    intent_source: str
    docs: list[dict]
    personalized_explanation: str
    check_question: str
    evaluation_result: dict
    mastery_event: dict
    complexity_decision: str
    complexity_reason: str
    complexity_retry_count: int
    answer: str
    remediation_explanation: str
    attempt_count: int
    check_answer_hint: str
    active_node: str
