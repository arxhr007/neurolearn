"""Node factory functions used by the LangGraph runtime."""

from langgraph_app.config import TOP_K
from langgraph_app.graph.mastery import process_mastery_side_effects
from langgraph_app.state import RAGState
from collections import OrderedDict
import hashlib
import json


# Simple in-memory LRU cache for personalizer outputs.
# Keyed by sha256(question + doc ids + student_profile summary).
_PERSONALIZER_CACHE: OrderedDict[str, str] = OrderedDict()
_PERSONALIZER_CACHE_MAX = 1024

# Simple in-memory LRU cache for judge results (label, reason)
_JUDGE_CACHE: OrderedDict[str, tuple[str, str]] = OrderedDict()
_JUDGE_CACHE_MAX = 4096


def _looks_like_insufficient_answer(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in (
            "not enough information",
            "unable to answer",
            "cannot answer",
            "could not find",
            "no relevant sources",
            "provided passages",
            "motham info",
            "no direct passages",
            "not directly stated",
            "not available in the retrieved",
            "not enough direct",
            "no evidence",
            "വിവരമില്ല",
            "മതിയായ വിവര",
            "ലഭ്യമല്ല",
            "ഉത്തരം നൽകാൻ കഴിയില്ല",
            "ഉത്തരം നൽകാൻ സാധ്യമല്ല",
            "പ്രദത്തപ്പെട്ട രേഖകളിൽ",
            "കൊടുത്തിരിക്കുന്ന രേഖകളിൽ",
            "ലഭ്യമായ ഉറവിടങ്ങളിൽ നിന്ന്",
            "രേഖകളിൽ വിവരമില്ല",
            "വിവരണം ഇല്ലാത്തതിനാൽ",
        )
    )


def make_parent_orchestrator():
    def parent_orchestrator(state: RAGState) -> RAGState:
        return {"active_node": "parent_orchestrator"}

    return parent_orchestrator


def make_llm_intent_classifier(classifier):
    def intent_classifier(state: RAGState) -> RAGState:
        intent_input = state.get("student_response") or state.get("question", "")
        intent, source = classifier.classify_with_source(intent_input)
        print(f"   Intent classified as: {intent} ({source})")
        return {
            "intent": intent,
            "intent_source": source,
            "active_node": "intent_classifier",
        }

    return intent_classifier


def make_goal_drift_checker(llm, node_name: str = "goal_drift_checker"):
    def goal_drift_checker(state: RAGState) -> RAGState:
        if state.get("intent") == "smalltalk":
            return {
                "drift_detected": False,
                "drift_reason": "smalltalk",
                "active_node": node_name,
            }

        if state.get("check_answer_hint"):
            return {
                "drift_detected": False,
                "drift_reason": "answer_turn",
                "active_node": node_name,
            }

        question = state.get("question", "")
        student_profile = state.get("student_profile")
        goal_text = str(state.get("active_learning_goal") or "").strip()

        if not goal_text:
            student_db = state.get("student_db")
            student_id = state.get("student_id")
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
        no_docs = not docs
        if no_docs:
            print("   No relevant passages found.")

        return {
            "docs": docs,
            "no_docs_found": bool(no_docs),
            "active_node": node_name,
        }

    return knowledge_retriever


def make_smalltalk_responder(llm, node_name: str = "smalltalk_responder"):
    def smalltalk_responder(state: RAGState) -> RAGState:
        text = state.get("student_response") or state.get("question", "")
        print(f"   Smalltalk responder running for node: {node_name}")
        reply = llm.generate_smalltalk(text)
        return {
            "answer": reply,
            "evaluation_result": {"smalltalk": True},
            "active_node": node_name,
        }

    return smalltalk_responder


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
        # Short-circuit if retriever found no documents
        if state.get("no_docs_found") or not (state.get("docs") or []):
            print(f"   Personalizer short-circuited for node: {node_name} (no docs)")
            question = state.get("question", "")
            profile = state.get("student_profile") or {}
            explanation = llm.generate_general_answer(question, profile)
            return {
                "personalized_explanation": explanation,
                "answer": explanation,
                "no_docs_found": True,
                "general_answer_fallback": True,
                "active_node": node_name,
            }

        # Compute a stable cache key based on question, docs ids, and a small
        # fingerprint of the student profile to avoid repeated LLM calls.
        question = state.get("question", "")
        docs = state.get("docs", [])
        profile = state.get("student_profile") or {}

        doc_ids = [str(d.get("chunk_id") or d.get("id") or d.get("source") or "") for d in docs]
        key_payload = {"q": question, "docs": doc_ids, "profile": {k: profile.get(k) for k in sorted(profile) if k in ("learning_style", "reading_age")}}
        key_raw = json.dumps(key_payload, sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

        # Check cache
        if key in _PERSONALIZER_CACHE:
            explanation = _PERSONALIZER_CACHE[key]
            # move to end to mark recent use
            _PERSONALIZER_CACHE.move_to_end(key)
            print(f"   Personalizer cache hit for node: {node_name}")
            return {"personalized_explanation": explanation, "answer": explanation, "active_node": node_name}

        print(f"   Personalizer running for node: {node_name}")
        explanation = llm.personalize(
            question,
            docs,
            profile,
        )
        if _looks_like_insufficient_answer(explanation):
            print(f"   Personalizer fallback triggered for node: {node_name} (insufficient grounding)")
            explanation = llm.generate_general_answer(question, profile)
            return {
                "personalized_explanation": explanation,
                "answer": explanation,
                "general_answer_fallback": True,
                "active_node": node_name,
            }

        # If the general answer itself still looks like a refusal, force one more fallback.
        if _looks_like_insufficient_answer(explanation):
            explanation = (
                "ഈ വിഷയം പൊതുവായി പറഞ്ഞാൽ, മനസ്സിലാക്കാൻ ലളിതമായ രീതിയിൽ മറുപടി നൽകാം. "
                "കൂടുതൽ വിശദമായ explanation വേണമെങ്കിൽ ചോദ്യം അല്പം വ്യക്തമായി ചോദിക്കൂ."
            )
            return {
                "personalized_explanation": explanation,
                "answer": explanation,
                "general_answer_fallback": True,
                "active_node": node_name,
            }
        print("   Personalizer produced explanation")

        # Store in cache with simple size cap
        _PERSONALIZER_CACHE[key] = explanation
        if len(_PERSONALIZER_CACHE) > _PERSONALIZER_CACHE_MAX:
            _PERSONALIZER_CACHE.popitem(last=False)

        return {
            "personalized_explanation": explanation,
            "answer": explanation,
            "general_answer_fallback": False,
            "active_node": node_name,
        }

    return personalizer


def make_personalization_gate(llm, node_name: str = "personalization_gate"):
    def personalization_gate(state: RAGState) -> RAGState:
        explanation = (state.get("personalized_explanation") or state.get("answer") or "").strip()
        retry_count = int(state.get("complexity_retry_count", 0))
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

        # Fast path: short, plain explanations do not need an LLM judge.
        clearly_simple = not clearly_over_complex and word_count < 80 and avg_word_len < 7.5 and explanation.count(".") <= 3
        if clearly_simple:
            label = "deliver"
            judge_reason = f"heuristic:deliver:words={word_count}:avg={avg_word_len:.2f}"
            print("   Gate A judge source: HEURISTIC")
        else:
            # Use a cached judge result when possible to avoid repeated LLM calls
            explanation_key = hashlib.sha256(explanation.encode("utf-8")).hexdigest()
            cached = _JUDGE_CACHE.get(explanation_key)
            if cached is not None:
                label, judge_reason = cached
                judge_source = "CACHE"
                # move to end to mark recent use
                _JUDGE_CACHE.move_to_end(explanation_key)
                print(f"   Gate A judge source: {judge_source}")
            else:
                label, judge_reason = llm.judge_personalization_complexity(explanation)
                judge_source = "LLM" if judge_reason.startswith("llm:") else "FALLBACK"
                print(f"   Gate A judge source: {judge_source}")
                # store in cache
                _JUDGE_CACHE[explanation_key] = (label, judge_reason)
                if len(_JUDGE_CACHE) > _JUDGE_CACHE_MAX:
                    _JUDGE_CACHE.popitem(last=False)

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
        if state.get("general_answer_fallback"):
            print(f"   Evaluator skipped for node: {node_name} (general answer fallback)")
            return {
                "evaluation_result": {
                    "status": "general_answer_fallback",
                    "is_correct": None,
                },
                "active_node": node_name,
            }

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
        # Short-circuit evaluation if retriever found no documents
        if state.get("no_docs_found") or not (state.get("docs") or []):
            msg = "No relevant sources found; unable to evaluate or provide an answer."
            print(f"   Answer evaluator short-circuited for node: {node_name} (no docs)")
            evaluation = {
                "is_correct": False,
                "feedback": msg,
                "confidence": 0.0,
                "source": "no_docs",
            }
            mastery_event = process_mastery_side_effects(state, evaluation)
            return {
                "evaluation_result": evaluation,
                "mastery_event": mastery_event,
                "no_docs_found": True,
                "active_node": node_name,
            }

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
