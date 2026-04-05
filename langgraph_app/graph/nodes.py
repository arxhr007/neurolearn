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


def make_knowledge_retriever(retriever, node_name: str = "knowledge_retriever"):
    def knowledge_retriever(state: RAGState) -> RAGState:
        question = state["question"]
        docs = retriever.query(question, top_k=state.get("top_k", TOP_K))
        return {
            "docs": docs,
            "active_node": node_name,
        }

    return knowledge_retriever


def make_answer_generator(llm, node_name: str = "answer_generator"):
    def answer_generator(state: RAGState) -> RAGState:
        answer = llm.generate(state["question"], state.get("docs", []))
        return {
            "answer": answer,
            "active_node": node_name,
        }

    return answer_generator


def make_personalizer(llm, node_name: str = "personalizer"):
    def personalizer(state: RAGState) -> RAGState:
        print(f"   Personalizer running for node: {node_name}")
        explanation = llm.personalize(
            state["question"],
            state.get("docs", []),
            state.get("student_profile"),
        )
        print("   Personalizer produced explanation")
        return {
            "personalized_explanation": explanation,
            "answer": explanation,
            "active_node": node_name,
        }

    return personalizer


def make_personalization_gate(llm, node_name: str = "personalization_gate"):
    def personalization_gate(state: RAGState) -> RAGState:
        explanation = (state.get("personalized_explanation") or state.get("answer") or "").strip()
        retry_count = int(state.get("complexity_retry_count", 0))
        label, judge_reason = llm.judge_personalization_complexity(explanation)
        judge_source = "LLM" if judge_reason.startswith("llm:") else "FALLBACK"
        print(f"   Gate A judge source: {judge_source}")
        words = explanation.split()
        word_count = len(words)
        avg_word_len = (sum(len(w) for w in words) / word_count) if word_count else 0.0

        # Strict policy: only revise if text is clearly over-complex.
        clearly_over_complex = (
            word_count >= 120
            or avg_word_len >= 9.0
            or explanation.count(";") >= 3
            or explanation.count(":") >= 3
        )
        if label == "revise" and not clearly_over_complex:
            print(
                "   Gate A override: revise -> deliver "
                f"(not clearly over-complex: words={word_count}, avg_word_len={avg_word_len:.2f})"
            )
            label = "deliver"
            judge_reason = f"{judge_reason}:override_not_overcomplex"

        if label == "revise" and retry_count == 0:
            reason = f"too_complex: {judge_reason}; simplify once and retry"
            decision = "revise"
            next_retry_count = retry_count + 1
            print("   Gate A action: revise -> loop back to personalizer")
        elif label == "revise" and retry_count > 0:
            reason = f"retry_cap_reached: {judge_reason}; delivering after one retry"
            decision = "deliver"
            next_retry_count = retry_count
            print("   Gate A action: deliver -> retry cap reached")
        else:
            reason = f"ok: {judge_reason}; safe to deliver"
            decision = "deliver"
            next_retry_count = retry_count
            print("   Gate A action: deliver -> send to user")

        print(f"   Gate A check: {reason} (retry_count={retry_count})")

        return {
            "complexity_decision": decision,
            "complexity_reason": reason,
            "complexity_retry_count": next_retry_count,
            "active_node": node_name,
        }

    return personalization_gate


def make_evaluator(llm, node_name: str = "evaluator"):
    def evaluator(state: RAGState) -> RAGState:
        explanation = (state.get("personalized_explanation") or state.get("answer") or "").strip()
        question = state.get("question", "")
        student_profile = state.get("student_profile")
        check_question = llm.generate_check_question(question, explanation, student_profile)

        print(f"   Evaluator generated check question: {check_question}")

        return {
            "check_question": check_question,
            "evaluation_result": {
                "status": "check_question_generated",
                "check_question": check_question,
            },
            "active_node": node_name,
        }

    return evaluator
