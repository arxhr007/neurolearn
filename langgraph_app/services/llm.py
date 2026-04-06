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
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"[{i}] (Source: {doc['source']}, Page {doc['page']})\n{doc['text']}"
            )
        context_block = "\n\n".join(context_parts)

        system_prompt = (
            "You are a strict answer evaluator for a Malayalam educational tutor. "
            "Compare the student's response with the retrieved context. "
            "Return exactly one JSON object with keys: is_correct (boolean), feedback (string), misconception (string), confidence (number). "
            "Do not return markdown, code fences, or extra text."
        )
        user_prompt = (
            f"Question/topic: {question}\n"
            f"Student response: {student_response}\n"
            f"Expected answer hint: {expected_answer_hint or ''}\n"
            f"Reading age: {reading_age}\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines for feedback style:\n{neuro_guidelines}\n"
            f"Context:\n{context_block}\n\n"
            "Rules:\n"
            "- is_correct should be true only if the student's response matches the context well.\n"
            "- feedback should be short, direct, and in Malayalam.\n"
            "- misconception should name the main mistake or be empty string if correct.\n"
            "- confidence should be a number from 0 to 1.\n"
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

        return {
            "is_correct": False,
            "feedback": "ഉത്തരം വിലയിരുത്താൻ കഴിഞ്ഞില്ല.",
            "misconception": "parse_failed",
            "confidence": 0.0,
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

