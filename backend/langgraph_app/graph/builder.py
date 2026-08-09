"""Build and compile the LangGraph application."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from langgraph_app.graph.nodes import (
    make_answer_evaluator,
    make_drift_redirect,
    make_evaluator,
    make_goal_drift_checker,
    make_llm_intent_classifier,
    make_knowledge_retriever,
    make_parent_orchestrator,
    make_personalization_gate,
    make_personalizer,
    make_remediation_node,
    make_smalltalk_responder,
)
from langgraph_app.state import RAGState


logger = logging.getLogger(__name__)
import time


def _wrap_node_with_timing(node_callable, node_name: str):
    """Wrap a node callable so it records per-node elapsed time into the state.

    The wrapped node returns the same state dict as the original node, but with
    an appended `node_timings` list containing dicts: {"node": name, "elapsed_ms": float}.
    """

    def wrapped(state: RAGState) -> RAGState:
        start = time.perf_counter()
        result = node_callable(state)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        try:
            # Ensure we have a mutable dict
            out = dict(result or {})
        except Exception:
            out = {"_raw_result": result}

        prev = list(state.get("node_timings", [])) if isinstance(state.get("node_timings"), list) else []
        prev.append({"node": node_name, "elapsed_ms": elapsed_ms})
        out["node_timings"] = prev
        logger.debug("Node %s took %.1f ms", node_name, elapsed_ms)
        return out

    return wrapped


def _normalize_sqlite_conn_string(checkpoint_path: str) -> str:
    """Normalize checkpoint input into a SqliteSaver connection string."""
    raw = str(checkpoint_path or "").strip()
    if raw.startswith("sqlite:"):
        return raw
    path = Path(raw).expanduser().resolve()
    return f"sqlite:///{path.as_posix()}"


def build_graph_app(
    retriever: Any,
    llm: Any,
    intent_classifier: Any,
    checkpoint_path: str | None = None,
) -> Any:
    def route_by_intent_with_drift(state: RAGState) -> str:
        if state.get("check_answer_hint"):
            return "answer_retriever"
        intent = state.get("intent", "new_concept")
        if intent == "smalltalk":
            return "smalltalk_responder"
        if state.get("drift_detected", False):
            return "drift_redirect"
        return "answer_retriever" if intent == "answer" else "new_concept_retriever"

    def route_by_correctness(state: RAGState) -> str:
        is_correct = state.get("evaluation_result", {}).get("is_correct", True)
        return "END" if is_correct else "remediation"

    def initialize_gate_state(state: RAGState) -> RAGState:
        return {"complexity_retry_count": int(state.get("complexity_retry_count", 0))}

    graph = StateGraph(RAGState)
    graph.add_node("parent_orchestrator", _wrap_node_with_timing(make_parent_orchestrator(), "parent_orchestrator"))
    graph.add_node("intent_classifier", _wrap_node_with_timing(make_llm_intent_classifier(intent_classifier), "intent_classifier"))
    graph.add_node(
        "goal_drift_checker",
        _wrap_node_with_timing(make_goal_drift_checker(llm, node_name="goal_drift_checker"), "goal_drift_checker"),
    )
    graph.add_node(
        "drift_redirect",
        _wrap_node_with_timing(make_drift_redirect(node_name="drift_redirect"), "drift_redirect"),
    )
    graph.add_node(
        "new_concept_retriever",
        _wrap_node_with_timing(make_knowledge_retriever(retriever, node_name="new_concept_retriever"), "new_concept_retriever"),
    )
    graph.add_node(
        "answer_retriever",
        _wrap_node_with_timing(make_knowledge_retriever(retriever, node_name="answer_retriever"), "answer_retriever"),
    )
    graph.add_node(
        "smalltalk_responder",
        _wrap_node_with_timing(make_smalltalk_responder(llm, node_name="smalltalk_responder"), "smalltalk_responder"),
    )
    graph.add_node(
        "new_concept_personalizer",
        _wrap_node_with_timing(make_personalizer(llm, node_name="new_concept_personalizer"), "new_concept_personalizer"),
    )
    graph.add_node(
        "personalization_gate",
        _wrap_node_with_timing(make_personalization_gate(llm, node_name="personalization_gate"), "personalization_gate"),
    )
    graph.add_node(
        "answer_evaluator",
        _wrap_node_with_timing(make_answer_evaluator(llm, node_name="answer_evaluator"), "answer_evaluator"),
    )
    graph.add_node(
        "evaluator",
        _wrap_node_with_timing(make_evaluator(llm, node_name="evaluator"), "evaluator"),
    )
    graph.add_node(
        "remediation",
        _wrap_node_with_timing(make_remediation_node(llm, node_name="remediation"), "remediation"),
    )

    def route_by_complexity(state: RAGState) -> str:
        decision = state.get("complexity_decision", "deliver")
        return "new_concept_personalizer" if decision == "revise" else "deliver_answer"

    graph.set_entry_point("parent_orchestrator")
    graph.add_edge("parent_orchestrator", "intent_classifier")
    graph.add_edge("intent_classifier", "goal_drift_checker")
    graph.add_conditional_edges(
        "goal_drift_checker",
        route_by_intent_with_drift,
        {
            "new_concept_retriever": "new_concept_retriever",
            "answer_retriever": "answer_retriever",
            "drift_redirect": "drift_redirect",
            "smalltalk_responder": "smalltalk_responder",
        },
    )
    graph.add_edge("new_concept_retriever", "new_concept_personalizer")
    graph.add_edge("new_concept_personalizer", "personalization_gate")
    graph.add_conditional_edges(
        "personalization_gate",
        route_by_complexity,
        {
            "new_concept_personalizer": "new_concept_personalizer",
            "deliver_answer": "evaluator",
        },
    )
    graph.add_edge("answer_retriever", "answer_evaluator")
    graph.add_conditional_edges(
        "answer_evaluator",
        route_by_correctness,
        {
            "remediation": "remediation",
            "END": END,
        },
    )
    graph.add_edge("evaluator", END)
    graph.add_edge("drift_redirect", END)
    graph.add_edge("remediation", END)
    graph.add_edge("smalltalk_responder", END)

    if checkpoint_path:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            conn_string = _normalize_sqlite_conn_string(checkpoint_path)
            checkpointer = SqliteSaver.from_conn_string(conn_string)
            return graph.compile(checkpointer=checkpointer)
        except Exception as exc:
            logger.warning("Checkpointing disabled due to error: %s", exc)
    return graph.compile()


def invoke_graph_safe(
    app: Any,
    payload: dict,
    timeout_seconds: int = 30,
    config: dict | None = None,
) -> dict:
    """Invoke graph with timeout and normalized error handling."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty dict")

    def _invoke() -> dict:
        return app.invoke(payload, config=config)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            return future.result(timeout=max(int(timeout_seconds), 1))
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"Graph invocation timed out after {timeout_seconds}s") from exc
    except Exception as exc:
        logger.exception("Graph invocation failed")
        raise RuntimeError(f"Graph invocation failed: {exc}") from exc


async def invoke_graph_async(
    app: Any,
    payload: dict,
    timeout_seconds: int = 30,
    config: dict | None = None,
) -> dict:
    """Async wrapper around invoke_graph_safe for web handlers."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(None, lambda: invoke_graph_safe(app, payload, timeout_seconds, config)),
        timeout=max(int(timeout_seconds), 1),
    )
