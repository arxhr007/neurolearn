"""Mastery tracking helpers used by answer evaluation nodes."""

import re


def _sanitize_component(text: str, fallback: str = "general") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return cleaned or fallback


def _build_semantic_concept_key(
    question: str,
    check_answer_hint: str,
    docs: list[dict],
    llm=None,
) -> tuple[str, str]:
    combined = f"{(question or '').lower()} {(check_answer_hint or '').lower()}"

    if llm is not None:
        try:
            llm_components = llm.normalize_concept_components(
                question=question,
                check_answer_hint=check_answer_hint,
                context_docs=docs,
            )
            if llm_components:
                return (
                    f"{_sanitize_component(str(llm_components.get('domain') or ''), 'general')}."
                    f"{_sanitize_component(str(llm_components.get('topic') or ''), 'topic')}."
                    f"{_sanitize_component(str(llm_components.get('skill') or ''), 'basics')}",
                    "llm",
                )
        except Exception:
            # Fall back to deterministic rules on any LLM normalization issue.
            pass

    rules = [
        (["കൈകഴുക", "handwash", "hand wash"], "hygiene", "handwashing"),
        (["പല്ല്", "tooth", "brush"], "hygiene", "toothbrushing"),
        (["ചെസ്", "chess"], "games", "chess"),
        (["ഫുട്ബോൾ", "football", "soccer"], "games", "football"),
        (["ശുചിത്വ", "hygiene"], "hygiene", "clean_habits"),
    ]

    domain = "general"
    topic = "topic"
    for tokens, d, t in rules:
        if any(token in combined for token in tokens):
            domain, topic = d, t
            break

    # Avoid source-filename derived keys; fallback stays semantic/generic.
    if domain == "general":
        topic = "topic"

    if any(token in combined for token in ["എങ്ങനെ", "how", "steps", "step", "രീതി", "ചുവട"]):
        skill = "steps"
    elif any(token in combined for token in ["എന്തുകൊണ്ട്", "why", "importance", "പ്രധാന"]):
        skill = "importance"
    elif any(token in combined for token in ["എത്ര", "how many", "സെക്കൻഡ്", "seconds", "time"]):
        skill = "fact"
    elif any(token in combined for token in ["എന്ത്", "which", "what"]):
        skill = "identify"
    else:
        skill = "basics"

    return f"{_sanitize_component(domain)}.{_sanitize_component(topic)}.{_sanitize_component(skill)}", "fallback"


def _build_concept_trace(docs: list[dict]) -> dict:
    if docs:
        top_doc = docs[0]
        page_val = top_doc.get("page")
        chunk_val = top_doc.get("chunk_id")
        return {
            "source_doc": str(top_doc.get("source") or ""),
            "source_page": int(page_val) if page_val is not None else None,
            "source_chunk_id": int(chunk_val) if chunk_val is not None else None,
        }

    return {
        "source_doc": "",
        "source_page": None,
        "source_chunk_id": None,
    }


def process_mastery_side_effects(state: dict, evaluation: dict) -> dict | None:
    """Persist mastery and trigger profile updates. Returns mastery event payload if saved."""
    student_db = state.get("student_db")
    student_id = state.get("student_id")
    if not student_db or not student_id:
        return None

    docs = state.get("docs", []) or []
    llm = state.get("llm")
    concept_key, concept_key_source = _build_semantic_concept_key(
        question=str(state.get("question") or ""),
        check_answer_hint=str(state.get("check_answer_hint") or ""),
        docs=docs,
        llm=llm,
    )
    concept_trace = _build_concept_trace(docs)
    mastery_event = None

    try:
        event_id = student_db.record_mastery_event(
            student_id=student_id,
            concept_key=concept_key,
            is_correct=bool(evaluation.get("is_correct", False)),
            misconception=str(evaluation.get("misconception") or ""),
            confidence=float(evaluation.get("confidence", 0.0)),
            source_doc=concept_trace.get("source_doc"),
            source_page=concept_trace.get("source_page"),
            source_chunk_id=concept_trace.get("source_chunk_id"),
        )
        mastery_event = {
            "id": event_id,
            "student_id": student_id,
            "concept_key": concept_key,
            "concept_key_source": concept_key_source,
            "source_doc": concept_trace.get("source_doc"),
            "source_page": concept_trace.get("source_page"),
            "source_chunk_id": concept_trace.get("source_chunk_id"),
            "is_correct": bool(evaluation.get("is_correct", False)),
            "misconception": str(evaluation.get("misconception") or ""),
            "confidence": float(evaluation.get("confidence", 0.0)),
        }
        print(
            "   Mastery recorded: "
            f"id={event_id} concept_key={concept_key} source={concept_key_source} "
            f"trace={concept_trace.get('source_doc')}::p{concept_trace.get('source_page')}"
        )
    except Exception as exc:
        print(f"   Mastery record failed: {exc}")

    try:
        updated_profile = student_db.update_profile_from_mastery(student_id, recent_limit=10)
        if updated_profile and updated_profile["reading_age"] != state.get("student_profile", {}).get("reading_age"):
            print("   Profile updated for next interaction")
    except Exception as exc:
        print(f"   Profile update failed: {exc}")

    return mastery_event
