"""Node factory functions used by the LangGraph runtime."""

from langgraph_app.config import TOP_K
from langgraph_app.intents.rules import classify_intent
from langgraph_app.state import RAGState


def make_parent_orchestrator():
    def parent_orchestrator(state: RAGState) -> RAGState:
        return {"active_node": "parent_orchestrator"}

    return parent_orchestrator


def make_intent_classifier():
    def intent_classifier(state: RAGState) -> RAGState:
        question = state["question"]
        intent = classify_intent(question)
        print(f"   Intent classified as: {intent}")
        return {
            "intent": intent,
            "active_node": "intent_classifier",
        }

    return intent_classifier


def make_llm_intent_classifier(classifier):
    def intent_classifier(state: RAGState) -> RAGState:
        question = state["question"]
        intent, source = classifier.classify_with_source(question)
        print(f"   Intent classified as: {intent} ({source})")
        return {
            "intent": intent,
            "intent_source": source,
            "active_node": "intent_classifier",
        }

    return intent_classifier


def make_knowledge_retriever(retriever):
    def knowledge_retriever(state: RAGState) -> RAGState:
        question = state["question"]
        docs = retriever.query(question, top_k=state.get("top_k", TOP_K))
        return {
            "docs": docs,
            "active_node": "knowledge_retriever",
        }

    return knowledge_retriever


def make_answer_generator(llm):
    def answer_generator(state: RAGState) -> RAGState:
        answer = llm.generate(state["question"], state.get("docs", []))
        return {
            "answer": answer,
            "active_node": "answer_generator",
        }

    return answer_generator
