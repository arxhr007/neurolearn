"""Build and compile the LangGraph application."""

from langgraph.graph import END, StateGraph

from langgraph_app.graph.nodes import (
    make_answer_generator,
    make_llm_intent_classifier,
    make_knowledge_retriever,
    make_parent_orchestrator,
    make_personalizer,
)
from langgraph_app.state import RAGState


def build_graph_app(retriever, llm, intent_classifier):
    def route_by_intent(state: RAGState) -> str:
        intent = state.get("intent", "new_concept")
        return "answer_retriever" if intent == "answer" else "new_concept_retriever"

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
        "answer_response_generator",
        make_answer_generator(llm, node_name="answer_response_generator"),
    )

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
    graph.add_edge("answer_retriever", "answer_response_generator")
    graph.add_edge("new_concept_personalizer", END)
    graph.add_edge("answer_response_generator", END)

    return graph.compile()
