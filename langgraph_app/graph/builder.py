"""Build and compile the LangGraph application."""

from langgraph.graph import END, StateGraph

from langgraph_app.graph.nodes import (
    make_answer_evaluator,
    make_evaluator,
    make_llm_intent_classifier,
    make_knowledge_retriever,
    make_parent_orchestrator,
    make_personalization_gate,
    make_personalizer,
)
from langgraph_app.state import RAGState


def build_graph_app(retriever, llm, intent_classifier):
    def route_by_intent(state: RAGState) -> str:
        intent = state.get("intent", "new_concept")
        return "answer_retriever" if intent == "answer" else "new_concept_retriever"

    def initialize_gate_state(state: RAGState) -> RAGState:
        return {"complexity_retry_count": int(state.get("complexity_retry_count", 0))}

    graph = StateGraph(RAGState)
    graph.add_node("parent_orchestrator", make_parent_orchestrator())
    graph.add_node("intent_classifier", make_llm_intent_classifier(intent_classifier))
    graph.add_node(
        "new_concept_retriever",
        make_knowledge_retriever(retriever, node_name="new_concept_retriever"),
    )
    graph.add_node(
        "answer_retriever",
        make_knowledge_retriever(retriever, node_name="answer_retriever"),
    )
    graph.add_node(
        "new_concept_personalizer",
        make_personalizer(llm, node_name="new_concept_personalizer"),
    )
    graph.add_node(
        "personalization_gate",
        make_personalization_gate(llm, node_name="personalization_gate"),
    )
    graph.add_node(
        "answer_evaluator",
        make_answer_evaluator(llm, node_name="answer_evaluator"),
    )
    graph.add_node(
        "evaluator",
        make_evaluator(llm, node_name="evaluator"),
    )

    def route_by_complexity(state: RAGState) -> str:
        decision = state.get("complexity_decision", "deliver")
        return "new_concept_personalizer" if decision == "revise" else "deliver_answer"

    graph.set_entry_point("parent_orchestrator")
    graph.add_edge("parent_orchestrator", "intent_classifier")
    graph.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "new_concept_retriever": "new_concept_retriever",
            "answer_retriever": "answer_retriever",
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
    graph.add_edge("evaluator", END)
    graph.add_edge("answer_evaluator", END)

    return graph.compile()
