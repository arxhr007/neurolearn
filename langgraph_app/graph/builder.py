"""Build and compile the LangGraph application."""

from langgraph.graph import END, StateGraph

from langgraph_app.graph.nodes import (
    make_answer_generator,
    make_llm_intent_classifier,
    make_knowledge_retriever,
    make_parent_orchestrator,
)
from langgraph_app.state import RAGState


def build_graph_app(retriever, llm, intent_classifier):
    graph = StateGraph(RAGState)
    graph.add_node("parent_orchestrator", make_parent_orchestrator())
    graph.add_node("intent_classifier", make_llm_intent_classifier(intent_classifier))
    graph.add_node("knowledge_retriever", make_knowledge_retriever(retriever))
    graph.add_node("answer_generator", make_answer_generator(llm))

    graph.set_entry_point("parent_orchestrator")
    graph.add_edge("parent_orchestrator", "intent_classifier")
    graph.add_edge("intent_classifier", "knowledge_retriever")
    graph.add_edge("knowledge_retriever", "answer_generator")
    graph.add_edge("answer_generator", END)

    return graph.compile()
