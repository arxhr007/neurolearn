"""Typed state shared across LangGraph nodes."""

from typing import TypedDict


class RAGState(TypedDict, total=False):
    question: str
    top_k: int
    intent: str
    intent_source: str
    docs: list[dict]
    answer: str
    active_node: str
