"""Typed state shared across LangGraph nodes."""

from typing import TypedDict


class RAGState(TypedDict, total=False):
    student_id: str
    question: str
    top_k: int
    student_profile: dict
    intent: str
    intent_source: str
    docs: list[dict]
    personalized_explanation: str
    answer: str
    active_node: str
