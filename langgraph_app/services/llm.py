"""Groq-backed LLM service."""

import os
import json
import re
import sys
import time

from groq import Groq

from langgraph_app.config import COMPLEXITY_JUDGE_MODEL, GROQ_MODEL, INTENT_MODEL, SYSTEM_PROMPT


class MalayalamLLM:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("ERROR: Set the GROQ_API_KEY environment variable.")
            print("  Get a free key at https://console.groq.com/keys")
            sys.exit(1)
        self.client = Groq(api_key=api_key)
        print(f"[LLM] Using Groq model: {GROQ_MODEL}")

    @staticmethod
    def _extract_response_text(response) -> str:
        """Handle Groq/OpenAI-compatible response payload variants safely."""
        message = None
        try:
            message = response.choices[0].message
            content = message.content
        except Exception:
            return ""

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text is not None:
                        parts.append(str(text))
                elif hasattr(item, "text"):
                    text = getattr(item, "text", None)
                    if text is not None:
                        parts.append(str(text))
            return "".join(parts).strip()

        text = str(content).strip() if content is not None else ""
        if text:
            return text

        # Some reasoning-first models may return empty content while exposing text in reasoning.
        if message is not None:
            reasoning = getattr(message, "reasoning", None)
            if reasoning:
                return str(reasoning).strip()
        return ""

    def _build_neuro_support_guidelines(self, student_profile: dict | None) -> tuple[list[str], str]:
        profile = student_profile or {}
        raw = profile.get("neuro_profile", ["general"])
        if isinstance(raw, str):
            tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        elif isinstance(raw, list):
            tags = [str(t).strip().lower() for t in raw if str(t).strip()]
        else:
            tags = ["general"]

        if not tags:
            tags = ["general"]

        rules: list[str] = []
        rules.append(
            "Interpret the listed neurodivergent conditions as support needs and adapt communication accordingly."
        )
        rules.append(
            "If a condition is uncommon or not explicitly known, still provide high-clarity, low-overload, supportive output."
        )
        rules.append(
            "Do not mention diagnosis labels in the final answer unless the user explicitly asks for them."
        )

        if "adhd" in tags:
            rules.extend(
                [
                    "Keep response concise and high-focus (short paragraphs).",
                    "Use clear step-by-step structure.",
                    "Highlight key points early.",
                ]
            )
        if "autism" in tags:
            rules.extend(
                [
                    "Use literal, predictable language; avoid ambiguity.",
                    "Keep a consistent format.",
                    "Avoid figurative language unless explained clearly.",
                ]
            )
        if "dyslexia" in tags:
            rules.extend(
                [
                    "Use simple words and shorter sentences.",
                    "Avoid dense/long lines and complex wording.",
                    "Prefer clear bullet-like structure where useful.",
                ]
            )

        recognized = {"general", "adhd", "autism", "dyslexia"}
        custom_conditions = [t for t in tags if t not in recognized]
        if custom_conditions:
            rules.extend(
                [
                    f"Custom condition labels provided: {custom_conditions}.",
                    "Infer suitable accommodations from these labels conservatively (clarity, predictability, reduced overload, actionable steps).",
                    "Prioritize readability and comprehension over stylistic complexity.",
                ]
            )

        if not rules:
            rules = ["Use clear, supportive, age-appropriate language."]

        joined = "\n".join(f"- {r}" for r in rules)
        return tags, joined

    def normalize_concept_components(
        self,
        question: str,
        check_answer_hint: str,
        context_docs: list[dict],
    ) -> dict | None:
        """Infer normalized domain/topic/skill components for mastery concept keys.

        Returns dict with keys {domain, topic, skill} when parsing succeeds,
        otherwise returns None so callers can apply deterministic fallback logic.
        """

        def _extract_json(text: str) -> dict | None:
            raw = (text or "").strip()
            if not raw:
                return None
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            candidate = match.group(0) if match else raw
            candidate = candidate.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(candidate)
            except Exception:
                return None
            return parsed if isinstance(parsed, dict) else None

        def _chat_json(messages: list[dict], max_tokens: int):
            # Prefer structured JSON responses when supported by the model.
            model_name = INTENT_MODEL or GROQ_MODEL
            try:
                return self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                msg = str(exc).lower()
                if "response_format" in msg or "unsupported" in msg or "invalid_request" in msg:
                    return self.client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=max_tokens,
                    )
                raise

        def _sanitize_component(text: str, fallback: str) -> str:
            cleaned = re.sub(r"[^a-z0-9_]+", "_", (text or "").lower()).strip("_")
            cleaned = re.sub(r"_+", "_", cleaned)
            return cleaned or fallback

        def _normalize_domain(text: str) -> str:
            value = _sanitize_component(text, "general")
            aliases = {
                "health": "hygiene",
                "cleanliness": "hygiene",
                "cleaning": "hygiene",
                "sports": "games",
                "play": "games",
                "daily_life": "life_skills",
                "everyday": "life_skills",
                "numbers": "math",
            }
            value = aliases.get(value, value)
            allowed = {
                "hygiene",
                "games",
                "life_skills",
                "science",
                "language",
                "math",
                "health",
                "general",
            }
            return value if value in allowed else "general"

        def _normalize_skill(text: str) -> str:
            value = _sanitize_component(text, "basics")
            aliases = {
                "procedure": "steps",
                "process": "steps",
                "reason": "importance",
                "benefits": "importance",
                "count": "fact",
                "define": "identify",
                "definition": "identify",
                "concept": "basics",
            }
            value = aliases.get(value, value)
            allowed = {"basics", "identify", "steps", "importance", "fact"}
            return value if value in allowed else "basics"

        def _normalize_topic(text: str) -> str:
            value = _sanitize_component(text, "topic")
            # Block source-file style or generic placeholders from becoming topics.
            if re.fullmatch(r"(pre|primary|secondary|care|group|vocational)[_0-9]*", value):
                return "topic"
            if value in {"content", "chapter", "lesson", "topic", "general"}:
                return "topic"

            aliases = {
                "hand_washing": "handwashing",
                "handwash": "handwashing",
                "washing_hands": "handwashing",
                "tooth_brushing": "toothbrushing",
                "football_game": "football",
                "soccer": "football",
                "hygiene_habits": "clean_habits",
                "cleanliness_habits": "clean_habits",
            }
            return aliases.get(value, value)

        context_lines = []
        for i, doc in enumerate((context_docs or [])[:2], 1):
            source = str(doc.get("source") or "")
            page = doc.get("page")
            text = str(doc.get("text") or "").replace("\n", " ").strip()
            text = text[:320] + ("..." if len(text) > 320 else "")
            context_lines.append(f"[{i}] source={source} page={page} text={text}")

        allowed_domains = "hygiene, games, life_skills, science, language, math, health, general"
        allowed_skills = "basics, identify, steps, importance, fact"

        system_prompt = (
            "You are a concept normalizer for educational mastery tracking. "
            "Return exactly one JSON object with keys: domain, topic, skill. "
            "Use lowercase snake_case English identifiers only. "
            "Keep each field short (1-3 tokens). "
            f"Domain must be one of: {allowed_domains}. "
            f"Skill must be one of: {allowed_skills}. "
            "Do not use source filenames as topic values. "
            "Do not return markdown, prose, or extra keys."
        )
        user_prompt = (
            f"Question: {question}\n"
            f"Expected answer hint: {check_answer_hint}\n"
            f"Retrieved context:\n{chr(10).join(context_lines) if context_lines else '[]'}\n\n"
            "Task:\n"
            "- Infer a broad domain (examples: hygiene, games, science, language).\n"
            "- Infer a specific topic under that domain.\n"
            "- Infer skill type (examples: basics, identify, steps, importance, fact).\n"
            "Return only JSON."
        )

        for attempt in range(3):
            try:
                response = _chat_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=150,
                )
                content = self._extract_response_text(response)
                parsed = _extract_json(content)
                if not parsed:
                    # One strict retry style before giving up this attempt.
                    strict = _chat_json(
                        messages=[
                            {"role": "system", "content": "Return ONLY JSON: {\"domain\":\"...\",\"topic\":\"...\",\"skill\":\"...\"}"},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=80,
                    )
                    parsed = _extract_json(self._extract_response_text(strict))
                    if not parsed:
                        continue

                domain = _normalize_domain(str(parsed.get("domain") or ""))
                topic = _normalize_topic(str(parsed.get("topic") or ""))
                skill = _normalize_skill(str(parsed.get("skill") or ""))

                return {
                    "domain": domain,
                    "topic": topic,
                    "skill": skill,
                }
            except Exception as exc:
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(2 ** attempt * 3)
                else:
                    break

        return None

    def generate(self, question: str, context_docs: list[dict]) -> str:
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\\n{doc['text']}"
            )
        context_block = "\\n\\n".join(context_parts)

        user_prompt = f"Context:\\n{context_block}\\n\\nQuestion: {question}\\n\\nAnswer in Malayalam:"

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
                text = self._extract_response_text(response)
                if text:
                    return text
                raise RuntimeError("Empty answer content returned by LLM.")
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    def personalize(self, question: str, context_docs: list[dict], student_profile: dict | None = None) -> str:
        """Generate a personalized explanation using learner profile hints."""
        profile = student_profile or {}
        learning_style = profile.get("learning_style", "analogy-heavy")
        reading_age = profile.get("reading_age", 12)
        interest_graph = profile.get("interest_graph", [])
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\\n{doc['text']}"
            )
        context_block = "\\n\\n".join(context_parts)

        user_prompt = (
            f"Context:\\n{context_block}\\n\\n"
            f"Question: {question}\\n"
            f"Learning style: {learning_style}\\n"
            f"Reading age: {reading_age}\\n"
            f"Interest keywords: {interest_graph}\\n\\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\n\n"
            "Task:\\n"
            "- Answer in Malayalam.\\n"
            "- Keep vocabulary appropriate for the reading age.\\n"
            "- Use simple analogies aligned with interest keywords when relevant.\\n"
            "- Stay grounded in provided context and cite source numbers briefly.\\n"
            "- Keep response concise and student-friendly.\\n\\n"
            "Personalized Answer in Malayalam:"
        )

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    def generate_check_question(
        self,
        question: str,
        explanation: str,
        student_profile: dict | None = None,
    ) -> str:
        """Generate a single check-for-understanding question in Malayalam."""
        bundle = self.generate_check_question_bundle(question, explanation, student_profile)
        return str(bundle.get("question") or "").strip()

    def generate_check_question_bundle(
        self,
        question: str,
        explanation: str,
        student_profile: dict | None = None,
    ) -> dict:
        """Generate a check question plus a hidden expected-answer hint."""
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        system_prompt = (
            "You are an educational evaluator for a Malayalam tutor. "
            "Generate exactly one short check-for-understanding question in Malayalam and a hidden expected-answer hint. "
            "Do not include any extra commentary. "
            "Return exactly one JSON object with keys: question, expected_answer. "
            "Keep it simple, direct, and age-appropriate. "
            "Do not include numbering, bullets, or extra text."
        )
        user_prompt = (
            f"Original question: {question}\n"
            f"Personalized explanation: {explanation}\n"
            f"Reading age: {reading_age}\n\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\n\n"
            "Task: Write one short Malayalam question that checks understanding of the explanation.\n"
            "Also provide a short expected answer hint that can be used later to judge the student's answer.\n"
            "Keep the question to one sentence if possible.\n"
            "Return only the JSON object."
        )

        def _extract_json(text: str) -> dict | None:
            raw = (text or "").strip()
            if not raw:
                return None
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            candidate = match.group(0) if match else raw
            candidate = candidate.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(candidate)
            except Exception:
                return None
            if isinstance(parsed, dict):
                return parsed
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=256,
                )
                content = response.choices[0].message.content or ""
                parsed = _extract_json(content)
                if parsed:
                    parsed.setdefault("question", "")
                    parsed.setdefault("expected_answer", "")
                    return parsed
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 5
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise

        return {
            "question": "ഉത്തരം എഴുതുക.",
            "expected_answer": "",
        }

    def evaluate_student_answer(
        self,
        question: str,
        student_response: str,
        context_docs: list[dict],
        student_profile: dict | None = None,
        expected_answer_hint: str | None = None,
    ) -> dict:
        """Judge whether a student response is correct using retrieved context."""
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, _ = self._build_neuro_support_guidelines(student_profile)

        def _clip(text: str, limit: int = 280) -> str:
            cleaned = (text or "").strip().replace("\n", " ")
            if len(cleaned) <= limit:
                return cleaned
            return cleaned[: limit - 3].rstrip() + "..."

        context_parts = []
        for i, doc in enumerate(context_docs[:3], 1):
            context_parts.append(
                f"[{i}] {doc['source']} p.{doc['page']}: {_clip(str(doc['text']), 320)}"
            )
        context_block = "\n\n".join(context_parts)

        system_prompt = (
            "You are a strict answer evaluator for a Malayalam educational tutor. "
            "Return exactly one compact JSON object with keys: is_correct, feedback, misconception, confidence. "
            "Use Malayalam in feedback. Keep the JSON short. Do not include markdown, code fences, or extra text."
        )
        user_prompt = (
            f"Question/topic: {question}\n"
            f"Student response: {student_response}\n"
            f"Expected answer hint: {_clip(expected_answer_hint or '', 180)}\n"
            f"Reading age: {reading_age}\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Context:\n{context_block}\n\n"
            "Rules:\n"
            "- is_correct: true only if the response clearly matches the context and hint.\n"
            "- feedback: one short Malayalam sentence.\n"
            "- misconception: short label or empty string.\n"
            "- confidence: number between 0 and 1.\n"
            "Return only the JSON object."
        )

        def _extract_json(text: str) -> dict | None:
            raw = (text or "").strip()
            if not raw:
                return None
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            candidate = match.group(0) if match else raw
            candidate = candidate.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(candidate)
            except Exception:
                return None
            if isinstance(parsed, dict):
                return parsed
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=512,
                )
                content = response.choices[0].message.content or ""
                print(f"   Answer evaluator raw: {content!r}")
                parsed = _extract_json(content)
                if parsed:
                    parsed.setdefault("is_correct", False)
                    parsed.setdefault("feedback", "")
                    parsed.setdefault("misconception", "")
                    parsed.setdefault("confidence", 0.0)
                    return parsed
            except Exception as exc:
                if attempt == max_retries - 1:
                    break
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(2 ** attempt * 5)

        # Lightweight fallback so the evaluator still produces a useful result if
        # the model returns empty/truncated output.
        fallback_feedback = "ഉത്തരം കൂടുതൽ വ്യക്തമാക്കണം."
        fallback_misconception = "parse_failed"
        if expected_answer_hint and student_response:
            hint_words = {w for w in re.findall(r"[\wാ-്]+", expected_answer_hint.lower()) if len(w) > 2}
            response_words = {w for w in re.findall(r"[\wാ-്]+", student_response.lower()) if len(w) > 2}
            overlap = len(hint_words & response_words)
            if overlap >= 2:
                return {
                    "is_correct": True,
                    "feedback": "ശരി.",
                    "misconception": "",
                    "confidence": 0.7,
                }

        return {
            "is_correct": False,
            "feedback": fallback_feedback,
            "misconception": fallback_misconception,
            "confidence": 0.2,
        }

    def judge_personalization_complexity(self, explanation: str) -> tuple[str, str]:
        """Judge whether a personalized explanation is too complex to deliver."""
        system_prompt = (
            "You are a strict complexity judge for a Malayalam educational tutor. "
            "Decide whether the explanation is too complex for a student. "
            "Be conservative with REVISE: choose REVISE only if the text is clearly over-complex "
            "(too long, dense, jargon-heavy, or hard to read for students). "
            "Otherwise choose DELIVER. "
            "Return only one XML tag: <label>REVISE</label> or <label>DELIVER</label>."
        )
        user_prompt = (
            "Evaluate this explanation for complexity, length, and readability for a student.\n\n"
            f"Explanation:\n{explanation}\n\n"
            "If text is too complex, return <label>REVISE</label>. "
            "Otherwise return <label>DELIVER</label>."
        )

        def _normalize_label(raw: str) -> str | None:
            text = (raw or "").strip().lower()
            if not text:
                return None

            xml_match = re.search(r"<label>\s*(revise|deliver)\s*</label>", text)
            if xml_match:
                return xml_match.group(1)

            # Prefer exact labels, but tolerate surrounding text.
            match = re.search(r"\b(revise|deliver)\b", text)
            if match:
                return match.group(1)

            # Common model paraphrases or explanations.
            if any(token in text for token in ("too complex", "simplify", "needs simplification", "hard to read")):
                return "revise"
            if any(token in text for token in ("safe to deliver", "okay to deliver", "deliver", "good to send", "clear enough")):
                return "deliver"

            return None

        def _extract_text(response) -> str:
            try:
                content = response.choices[0].message.content
            except Exception:
                return ""

            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif hasattr(item, "text"):
                        parts.append(str(getattr(item, "text")))
                return "".join(parts)
            return ""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=COMPLEXITY_JUDGE_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=32,
                )
                raw_label = _extract_text(response)
                finish_reason = getattr(response.choices[0], "finish_reason", "unknown")
                print(f"   Gate A judge raw: {raw_label!r} (finish_reason={finish_reason})")
                label = _normalize_label(raw_label)
                if label:
                    reason = f"llm:{label}:model={COMPLEXITY_JUDGE_MODEL}"
                    return label, reason

                # Retry immediately with a stricter token-only prompt.
                strict_response = self.client.chat.completions.create(
                    model=COMPLEXITY_JUDGE_MODEL,
                    messages=[
                        {"role": "system", "content": "Return exactly one token: REVISE or DELIVER."},
                        {
                            "role": "user",
                            "content": (
                                "Classify the explanation complexity for a student. "
                                "Output only REVISE or DELIVER.\n\n"
                                f"Explanation:\n{explanation}"
                            ),
                        },
                    ],
                    temperature=0.0,
                    max_tokens=8,
                )
                strict_raw = _extract_text(strict_response)
                strict_finish = getattr(strict_response.choices[0], "finish_reason", "unknown")
                print(f"   Gate A strict judge raw: {strict_raw!r} (finish_reason={strict_finish})")
                strict_label = _normalize_label(strict_raw)
                if strict_label:
                    return strict_label, f"llm:{strict_label}:model={COMPLEXITY_JUDGE_MODEL}:strict"
            except Exception as exc:
                if attempt == max_retries - 1:
                    break
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(2 ** attempt * 5)

        # Final fallback should be conservative: only revise if clearly long.
        word_count = len(explanation.split())
        label = "revise" if word_count > 120 else "deliver"
        return label, f"fallback:{label}:words={word_count}"

    def generate_remediation(
        self,
        question: str,
        student_response: str,
        evaluator_feedback: str,
        context_docs: list[dict],
        student_profile: dict | None = None,
    ) -> str:
        """Generate a simpler, corrected explanation after incorrect answer."""
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\n{doc['text']}"
            )
        context_block = "\n\n".join(context_parts)

        system_prompt = (
            "You are a compassionate Malayalam tutor. "
            "Help a student learn from their mistake by providing a simpler, clearer explanation. "
            "Be encouraging and focus on the correct core concept in very simple words."
        )
        user_prompt = (
            f"Question/topic: {question}\n"
            f"Student's response: {student_response}\n"
            f"Evaluator feedback: {evaluator_feedback}\n"
            f"Reading age: {reading_age}\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\n"
            f"Context:\n{context_block}\n\n"
            "Task:\n"
            "- Explain the core concept in very simple Malayalam (shorter and clearer than before).\n"
            "- Use everyday examples the student might relate to.\n"
            "- Show what the correct answer should focus on.\n"
            "- Keep it brief (2-3 sentences max).\n"
            "- End with a hint for trying again.\n\n"
            "Remediation explanation in Malayalam:"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    max_tokens=512,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt * 10
                        print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                else:
                    raise

        return "പഠനം വീണ്ടും ശ്രമിക്കുക. നിങ്ങൾ കഴിവുള്ള കുട്ടിയാണ്." # Fallback encouragement message

    def check_learning_goal_drift(
        self,
        question: str,
        learning_goal: str,
        student_profile: dict | None = None,
    ) -> dict:
        """Detect if user query drifts from the active learning goal."""
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        system_prompt = (
            "You are a strict learning-goal alignment checker for a Malayalam tutor. "
            "Decide whether the student query is on-goal or off-goal with respect to the active learning goal. "
            "Return exactly one JSON object with keys: is_on_goal (boolean), reason (string), redirect_message (string). "
            "If is_on_goal is true, redirect_message should be empty string. "
            "If is_on_goal is false, redirect_message should be a short Malayalam message that gently refocuses the student on the goal."
        )
        user_prompt = (
            f"Active learning goal: {learning_goal}\n"
            f"Student query: {question}\n"
            f"Reading age: {reading_age}\n\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines for redirect message:\n{neuro_guidelines}\n\n"
            "Rules:\n"
            "- is_on_goal=true only when the query is clearly aligned to the goal topic.\n"
            "- reason should be short and in English.\n"
            "- redirect_message should be simple Malayalam and suggest a relevant question.\n"
            "Return only the JSON object."
        )

        def _extract_json(text: str) -> dict | None:
            raw = (text or "").strip()
            if not raw:
                return None
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            candidate = match.group(0) if match else raw
            candidate = candidate.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(candidate)
            except Exception:
                return None
            if isinstance(parsed, dict):
                return parsed
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=256,
                )
                content = response.choices[0].message.content or ""
                print(f"   Goal drift checker raw: {content!r}")
                parsed = _extract_json(content)
                if parsed:
                    parsed.setdefault("is_on_goal", True)
                    parsed.setdefault("reason", "aligned")
                    parsed.setdefault("redirect_message", "")
                    return parsed
            except Exception as exc:
                if attempt == max_retries - 1:
                    break
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(2 ** attempt * 5)

        return {
            "is_on_goal": True,
            "reason": "fallback_aligned",
            "redirect_message": "",
        }

