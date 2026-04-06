"""Node factory functions used by the LangGraph runtime."""

from langgraph_app.config import TOP_K
from langgraph_app.graph.mastery import process_mastery_side_effects
from langgraph_app.state import RAGState


def make_parent_orchestrator():
    def parent_orchestrator(state: RAGState) -> RAGState:
        return {"active_node": "parent_orchestrator"}

    return parent_orchestrator


def make_llm_intent_classifier(classifier):
    def intent_classifier(state: RAGState) -> RAGState:
        forced_intent = state.get("force_intent")
        if forced_intent in ("new_concept", "answer"):
            print(f"   Intent classified as: {forced_intent} (forced)")
            return {
                "intent": forced_intent,
                "intent_source": "forced",
                "active_node": "intent_classifier",
            }

        question = state["question"]
        intent, source = classifier.classify_with_source(question)
        print(f"   Intent classified as: {intent} ({source})")
        return {
            "intent": intent,
            "intent_source": source,
            "active_node": "intent_classifier",
        }

    return intent_classifier


def make_goal_drift_checker(llm, node_name: str = "goal_drift_checker"):
    def goal_drift_checker(state: RAGState) -> RAGState:
        student_db = state.get("student_db")
        student_id = state.get("student_id")
        question = state.get("question", "")
        student_profile = state.get("student_profile")

        if not student_db or not student_id:
            return {
                "drift_detected": False,
                "drift_reason": "no_student_context",
                "active_node": node_name,
            }

        goal = student_db.get_active_learning_goal(student_id)
        if not goal:
            return {
                "drift_detected": False,
                "drift_reason": "no_active_goal",
                "active_node": node_name,
            }

        goal_text = str(goal.get("goal_text") or "").strip()
        if not goal_text:
            return {
                "drift_detected": False,
                "drift_reason": "empty_goal",
                "active_node": node_name,
            }

        result = llm.check_learning_goal_drift(
            question=question,
            learning_goal=goal_text,
            student_profile=student_profile,
        )
        is_on_goal = bool(result.get("is_on_goal", True))
        drift_detected = not is_on_goal
        drift_reason = str(result.get("reason") or "aligned")
        drift_message = str(result.get("redirect_message") or "")

        print(f"   Goal drift check: drift_detected={drift_detected} reason={drift_reason}")

        return {
            "active_learning_goal": goal_text,
            "drift_detected": drift_detected,
            "drift_reason": drift_reason,
            "drift_message": drift_message,
            "active_node": node_name,
        }

    return goal_drift_checker


def make_drift_redirect(node_name: str = "drift_redirect"):
    def drift_redirect(state: RAGState) -> RAGState:
        goal_text = state.get("active_learning_goal") or "നിലവിലെ പഠനലക്ഷ്യം"
        redirect_message = state.get("drift_message") or (
            "നമുക്ക് ഇപ്പോഴത്തെ പഠനലക്ഷ്യത്തിലേക്ക് തിരികെ പോവാം. "
            f"ലക്ഷ്യം: {goal_text}. "
            "ഇതുമായി ബന്ധപ്പെട്ട ഒരു ചോദ്യം ചോദിക്കാമോ?"
        )
        return {
            "answer": redirect_message,
            "active_node": node_name,
        }

    return drift_redirect


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
        bundle = llm.generate_check_question_bundle(question, explanation, student_profile)
        check_question = str(bundle.get("question") or "").strip()
        check_answer_hint = str(bundle.get("expected_answer") or "").strip()

        print(f"   Evaluator generated check question: {check_question}")

        return {
            "check_question": check_question,
            "check_answer_hint": check_answer_hint,
            "evaluation_result": {
                "status": "check_question_generated",
                "check_question": check_question,
            },
            "active_node": node_name,
        }

    return evaluator


def make_answer_evaluator(llm, node_name: str = "answer_evaluator"):
    def answer_evaluator(state: RAGState) -> RAGState:
        student_response = state.get("student_response") or state.get("question", "")
        print(f"   Answer evaluator running for node: {node_name}")
        evaluation = llm.evaluate_student_answer(
            state.get("question", ""),
            student_response,
            state.get("docs", []),
            state.get("student_profile"),
            state.get("check_answer_hint"),
        )
        print(f"   Answer evaluator result: is_correct={evaluation.get('is_correct')} feedback={evaluation.get('feedback')}")
        mastery_event = process_mastery_side_effects(state, evaluation)

        return {
            "evaluation_result": evaluation,
            "mastery_event": mastery_event,
            "active_node": node_name,
        }

    return answer_evaluator


def make_remediation_node(llm, node_name: str = "remediation"):
    def remediation(state: RAGState) -> RAGState:
        is_correct = state.get("evaluation_result", {}).get("is_correct", True)
        if is_correct:
            return {"active_node": node_name}

        print(f"   Remediation node running for node: {node_name}")
        question = state.get("question", "")
        student_response = state.get("student_response", "")
        evaluation = state.get("evaluation_result", {})
        feedback = evaluation.get("feedback", "ഉത്തരം ശരിയായിരുന്നില്ല.")
        docs = state.get("docs", [])
        student_profile = state.get("student_profile")

        remediation_explanation = llm.generate_remediation(
            question=question,
            student_response=student_response,
            evaluator_feedback=feedback,
            context_docs=docs,
            student_profile=student_profile,
        )

        attempt_count = int(state.get("attempt_count", 0)) + 1
        print(f"   Remediation explanation generated (attempt {attempt_count})")

        return {
            "remediation_explanation": remediation_explanation,
            "attempt_count": attempt_count,
            "active_node": node_name,
        }

    return remediation
