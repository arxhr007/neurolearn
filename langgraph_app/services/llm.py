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
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)

        system_prompt = (
            "You are an educational evaluator for a Malayalam tutor. "
            "Generate exactly one short check-for-understanding question in Malayalam. "
            "Do not answer the question. "
            "Keep it simple, direct, and age-appropriate. "
            "Do not include numbering, bullets, or extra text."
        )
        user_prompt = (
            f"Original question: {question}\n"
            f"Personalized explanation: {explanation}\n"
            f"Reading age: {reading_age}\n\n"
            "Task: Write one short Malayalam question that checks understanding of the explanation.\n"
            "Keep it to one sentence if possible.\n"
            "Output only the question text."
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
                    temperature=0.2,
                    max_tokens=256,
                )
                content = response.choices[0].message.content or ""
                return content.strip()
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 5
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    def evaluate_student_answer(
        self,
        question: str,
        student_response: str,
        context_docs: list[dict],
        student_profile: dict | None = None,
    ) -> dict:
        """Judge whether a student response is correct using retrieved context."""
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)

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
            f"Reading age: {reading_age}\n"
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

