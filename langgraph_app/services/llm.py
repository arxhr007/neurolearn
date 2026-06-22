"""LLM service with Groq (primary) and Gemini (fallback) support."""

import os
import json
import re
import time

from groq import Groq

from langgraph_app.config import COMPLEXITY_JUDGE_MODEL, GROQ_MODEL, INTENT_MODEL, SYSTEM_PROMPT


def _gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class MalayalamLLM:
    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is required. Set it in the environment or .env file."
            )
        self.client = Groq(api_key=self.groq_api_key)

        self.gemini_api_key = os.environ.get("gemini_api_key") or ""
        self._gemini_model = None

        print(f"[LLM] Using Groq model: {GROQ_MODEL}")
        if self.gemini_api_key:
            print(f"[LLM] Gemini fallback available (model: {_gemini_model()})")

    STORY_FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

    def _call_gemini(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096, temperature: float = 0.3, model: str | None = None) -> str:
        """Generate text via Google Gemini REST API."""
        if not self.gemini_api_key:
            raise RuntimeError("Gemini API key not configured")

        import urllib.request
        import json

        model_name = model or _gemini_model()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_api_key}"
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=60)
        body = json.loads(resp.read())

        candidates = body.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        raise RuntimeError("Empty Gemini response")

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

    def generate_general_answer(self, question: str, student_profile: dict | None = None) -> str:
        """Generate a concise general answer when retrieval is thin or missing.

        This is used as a UX fallback so the tutor can still respond helpfully
        even when the KB does not contain a direct match.
        """
        profile = student_profile or {}
        learning_style = profile.get("learning_style", "analogy-heavy")
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)

        user_prompt = (
            f"Question: {question}\\n"
            f"Learning style: {learning_style}\\n"
            f"Reading age: {reading_age}\\n"
            f"Neuro profile: {neuro_tags}\\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\\n\\n"
            "Task:\n"
            "- Answer in Malayalam script (Unicode U+0D00–U+0D7F) only. NO other languages.\n"
            "- Keep it concise, clear, and student-friendly.\n"
            "- If relevant, mention that this is a general explanation rather than a direct quote from the retrieved passages.\n"
            "- Do not say you cannot answer just because context is thin.\n\n"
            "General Answer in Malayalam:"
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
                    max_tokens=1024,
                )
                text = self._extract_response_text(response)
                if text:
                    return text
                raise RuntimeError("Empty general answer content returned by LLM.")
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 10
                    print(f"   Rate limited. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq API rate limit exceeded after all retries.")

    @staticmethod
    def looks_like_refusal(text: str) -> bool:
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
                "no direct passages",
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
            "- Answer in Malayalam script (Unicode U+0D00–U+0D7F) only. NO other languages.\\n"
            "- Keep vocabulary appropriate for the reading age.\\n"
            "- Use simple analogies aligned with interest keywords when relevant.\\n"
            "- Stay grounded in provided context but do NOT cite source numbers.\\n"
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

    def generate_smalltalk(self, text: str) -> str:
        """Generate a brief friendly Malayalam smalltalk response."""
        prompt = (
            "You are a friendly Malayalam tutor. "
            "Respond politely and briefly (1-2 sentences) in Malayalam script only. "
            "If the user is greeting or thanking you, reply warmly and invite a learning question. "
            "Do not introduce academic content unless asked. "
            "NEVER use non-Malayalam scripts.\n\n"
            f"User: {text}\n"
            "Reply in Malayalam:"
        )

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                    max_tokens=256,
                )
                text_out = self._extract_response_text(response)
                if text_out:
                    return text_out
                raise RuntimeError("Empty smalltalk content returned by LLM.")
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt * 6
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

    def generate_chapter_drill_bundle(
        self,
        chapter_name: str,
        topic: str,
        chapter_docs: list[dict] | None = None,
        student_profile: dict | None = None,
        question_index: int = 1,
        total_questions: int = 3,
        previous_questions: list[str] | None = None,
        review_focus: str | None = None,
    ) -> dict:
        """Generate one grounded chapter drill question and hidden answer hint."""

        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)
        previous_questions = previous_questions or []

        def _clip(text: str, limit: int = 240) -> str:
            cleaned = (text or "").strip().replace("\n", " ")
            if len(cleaned) <= limit:
                return cleaned
            return cleaned[: limit - 3].rstrip() + "..."

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

        context_parts = []
        for i, doc in enumerate((chapter_docs or [])[:4], 1):
            context_parts.append(
                f"[{i}] {doc.get('source')} p.{doc.get('page')}: {_clip(str(doc.get('text') or ''), 320)}"
            )
        context_block = "\n\n".join(context_parts) if context_parts else "[]"

        system_prompt = (
            "You are a Malayalam educational drill generator. "
            "Return exactly one compact JSON object with keys: question, expected_answer. "
            "Keep both fields short and age-appropriate. "
            "Do not include markdown, bullets, numbering, or extra text."
        )
        user_prompt = (
            f"Chapter: {chapter_name}\n"
            f"Topic: {topic}\n"
            f"Question number: {question_index}/{total_questions}\n"
            f"Reading age: {reading_age}\n"
            f"Previous questions: {previous_questions}\n"
            f"Review focus: {review_focus or ''}\n\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\n\n"
            f"Chapter context:\n{context_block}\n\n"
            "Task:\n"
            "- Write one short Malayalam drill question grounded in the chapter context.\n"
            "- Prefer simple, real-life or story-like wording when possible.\n"
            "- Avoid copying long sentences from the source text.\n"
            "- Provide a short hidden expected_answer hint that captures the intended idea.\n"
            "- If review_focus is provided, make the question simpler and closer to that focus.\n"
            "Return only the JSON object."
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
                    temperature=0.25,
                    max_tokens=256,
                )
                content = self._extract_response_text(response)
                parsed = _extract_json(content)
                if parsed:
                    parsed.setdefault("question", "")
                    parsed.setdefault("expected_answer", "")
                    return parsed
            except Exception as exc:
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(2 ** attempt * 5)
                else:
                    break

        fallback_topic = topic or chapter_name or "വിഷയം"
        return {
            "question": f"{fallback_topic} കുറിച്ച് ഒരു ചെറിയ ചോദ്യം പറയാമോ?",
            "expected_answer": fallback_topic,
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

        # Fast path: if the student's response already overlaps strongly with the
        # expected answer hint, we can skip the model and return the same result
        # this method would eventually infer as a fallback.
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

    @staticmethod
    def _strip_curriculum_metadata(text: str) -> str:
        """Remove assessment criteria, learning outcomes, homework, and metadata lines."""
        lines = text.split("\n")
        cleaned: list[str] = []
        skip_section = False
        skip_patterns = re.compile(
            r"^(വിലയിരുത്തല്‍|Assessment|Learning Outcome|Outcome|Rubric|Homework|"
            r"പ്രവര്‍ത്തനം\s+\d+|Activity\s+\d+|"
            r"പാഠം\s+\d+|Lesson\s+\d+|Notes|Teacher Notes|Materials Needed|"
            r"ആവശ്യമായ സാധനങ്ങള്‍|ലക്ഷ്യം|Objective|Goal|"
            r"നിര്‍ദേശങ്ങള്‍|Instructions|Steps|ചുവടുകള്‍)",
            re.IGNORECASE,
        )
        module_pattern = re.compile(r"(മൊഡ്യൂള്[‌‍]*\s*\d+|Module\s+\d+)", re.IGNORECASE)
        assessment_markers = re.compile(
            r"(വിലയിരുത്തല്‍|Assessment|Evaluation|മാർക്ക്|Score|Grade|"
            r"കുട്ടിക്ക്\s+.*(?:അറിയുന്നു|കഴിയും))",
            re.IGNORECASE,
        )
        curriculum_lang_pattern = re.compile(
            r"(പ്രവര്‍ത്തന[ംത്തിന്‍]*\s*\d*\s*മണിക്കൂര്‍|"
            r"മണിക്കൂര്‍\s*പ്രവര്‍ത്തന|"
            r"ഈ\s+പ്രവര്‍ത്തന|"
            r"പ്രവര്‍ത്തനത്തിന്റെ\s+ഉദ്ദേശം|"
            r"പ്രവര്‍ത്തന\s*നിര്‍ദേശം|"
            r"പ്രവര്‍ത്തന\s*ലക്ഷ്യം|"
            r"സമയം\s*\d+\s*മണിക്കൂര്‍)",
            re.IGNORECASE,
        )
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if skip_section:
                    continue
                cleaned.append("")
                continue
            if skip_patterns.match(stripped):
                skip_section = True
                continue
            if module_pattern.search(stripped) and any(c.isdigit() for c in stripped):
                skip_section = True
                continue
            if assessment_markers.search(stripped):
                skip_section = True
                continue
            if curriculum_lang_pattern.search(stripped):
                skip_section = True
                continue
            if skip_section:
                if stripped.endswith((":", ",-", ".")) and len(stripped) < 60:
                    continue
                if re.match(r"^\d+[\.\)]", stripped):
                    continue
                skip_section = False
            if re.match(r"^(അധ്യാപക|Teacher|Parent|രക്ഷാകർത്താവ്)", stripped, re.IGNORECASE):
                continue
            if "പോസ്റ്റുചെയ്യുക" in stripped or "പോസ്റ്റ് ചെയ്യുക" in stripped:
                stripped = stripped.replace("പോസ്റ്റുചെയ്യുക", "കാണിച്ചു").replace("പോസ്റ്റ് ചെയ്യുക", "കാണിച്ചു")
            cleaned.append(stripped)
        result = "\n".join(cleaned)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    def _validate_story_quality(self, source: str, story: str) -> list[str]:
        """Check for metadata leakage and poor narrative quality."""
        issues: list[str] = []

        # 1. Curriculum language leaked mid-sentence
        leakage_patterns = [
            (r"വിലയിരുത്തല്‍", "Assessment term leaked"),
            (r"Assessment", "English assessment term leaked"),
            (r"Learning Outcome", "Learning Outcome leaked"),
            (r"മൊഡ്യൂള്[‌‍]*\s*\d+", "Module number leaked"),
            (r"പ്രവര്‍ത്തനം\s*\d+", "Activity number leaked"),
            (r"പോസ്റ്റുചെയ്യുക", "Homework instruction leaked"),
            (r"കുട്ടിക്ക്\s+.*(?:അറിയുന്നു|കഴിയും)", "Evaluation criteria leaked"),
            (r"\bപ്രവര്‍ത്തന(?:ം|ത്തിന്|ത്തില്‍|ങ്ങള്‍)", "Curriculum term 'പ്രവര്‍ത്തനം' leaked"),
            (r"\d+\s*മണിക്കൂര്‍", "Time duration (മണിക്കൂര്‍) leaked"),
            (r"ലക്ഷ്യബോധം\s*[\)\]\n]", "Generic moral buzzword 'ലക്ഷ്യബോധം'"),
            (r"സഹകരണം\s*[\)\]\n]", "Generic moral buzzword 'സഹകരണം'"),
            (r"ശ്രദ്ധ\s*[\)\]\n]", "Generic moral buzzword 'ശ്രദ്ധ'"),
        ]
        for pat, msg in leakage_patterns:
            if re.search(pat, story, re.IGNORECASE):
                issues.append(msg)

        # 2. Paragraph count (minimum 4 for any real story)
        para_count = len([p for p in story.split("\n\n") if p.strip()])
        if para_count < 4:
            issues.append(f"Too few paragraphs ({para_count})")

        # 3. Named characters beyond defaults
        char_tokens = re.findall(r"[ഀ-ൿ]{3,}", story)
        skip_words = {
            "അനു", "അവന്", "അവള്", "അവർ", "അവര്",
            "അമ്മ", "അച്ഛൻ", "അച്ഛന്", "സ്കൂള്", "വീട്", "ക്ലാസ്സ്",
            "കുട്ടി", "കുട്ടികള്", "അധ്യാപിക", "അധ്യാപകന്",
        }
        unique_chars = len(set(t for t in char_tokens if t not in skip_words and len(t) >= 3))
        if unique_chars == 0:
            issues.append("No named characters beyond defaults")

        # 4. Narrative action verbs
        has_action = any(
            word in story for word in
            ["ചെയ്തു", "പറഞ്ഞു", "എടുത്തു", "നോക്കി", "പോയി", "വന്നു",
             "ഇരുന്നു", "എഴുന്നേറ്റു", "ഓടി", "ചാടി", "കരഞ്ഞു", "ചിരിച്ചു"]
        )
        if not has_action:
            issues.append("No narrative action verbs found")

        # 5. Measurement density — flag if 4+ numeric measurements
        measurements = re.findall(
            r"\d+\s*(?:മീറ്റര്‍|അടി|സെന്റീമീറ്റര്‍|കിലോ|ഗ്രാം|ലിറ്റര്‍|മണിക്കൂര്‍|മിനിറ്റ്)",
            story,
        )
        if len(measurements) >= 3:
            issues.append(f"High measurement density ({len(measurements)} measurements)")

        # 6. Pronoun inconsistency — both അവൾ and അവൻ in same story
        has_av = bool(re.search(r'\bഅവന്\b', story))
        has_al = bool(re.search(r'\bഅവള്\b', story))
        if has_av and has_al:
            issues.append("Pronoun inconsistency (both അവൻ and അവൾ used)")
        if 'അവള്‍മാര്‍' in story or 'അവൾമാർ' in story:
            issues.append("Non-standard plural 'അവള്‍മാര്‍' used")

        # 7. Instruction-style procedural sentences
        instruction_verbs = re.findall(
            r'(?:അധ്യാപിക|അധ്യാപകന്|ടീച്ചര്)\s+\S+\s+(?:നല്‍കി|പറഞ്ഞു|നിര്‍ദേശിച്ചു)',
            story,
        )
        if len(instruction_verbs) >= 2:
            issues.append(f"Instruction-style framing ({len(instruction_verbs)} instances)")

        # 7b. Procedural step wording
        procedural_phrases = [
            r"ആദ്യത്തെ\s+കുട്ടി",
            r"അടുത്ത\s+കുട്ടി",
            r"അവസാനത്തെ\s+കുട്ടി",
            r"ആദ്യമായി\s+എടുത്തു",
            r"അടുത്ത\s+വൃത്തത്തിലേക്ക്",
            r"വരിയുടെ\s+അവസാന",
            r"ഓരോ\s+കുട്ടിയും",
        ]
        for pat in procedural_phrases:
            if re.search(pat, story, re.IGNORECASE):
                issues.append(f"Procedural wording: '{pat}'")
                break

        # 8. Unused materials — materials listed within 2 sentences but never used
        material_words = [
            "തേങ്ങ", "ചോക്ക്", "വിസി", "വിസിൽ", "പേപ്പര്‍", "കത്രിക",
            "പെൻസിൽ", "റബ്ബർ", "സ്കെയിൽ", "ഗ്ലൂ", "പശ", "നിറം",
            "പെയിന്റ്", "ബ്രഷ്", "തുണി", "നൂല്‍", "സൂചി", "ബട്ടണ്‍",
            "സിപ്പ്", "മരം", "ഇരുമ്പ്", "പ്ലാസ്റ്റിക്", "ഗ്ലാസ്", "കവര്‍",
            "ചിപ്പ്", "സ്ട്രിപ്പ്", "ബോര്‍ഡര്‍", "ചട്ടം",
        ]
        found_materials = [m for m in material_words if m in story]
        if len(found_materials) >= 3:
            materials_used = any(
                word in story for word in
                ["എടുത്തു", "ഉപയോഗിച്ചു", "പിടിച്ചു", "മുറിച്ചു", "ഒട്ടിച്ചു",
                 "വെച്ചു", "ചേർത്തു", "നെയ്തു", "തൂക്കി", "വരച്ചു"]
            )
            if not materials_used:
                issues.append(f"Material listing without narrative use ({found_materials})")

        # 9. Measurement anomaly — absurd values like 442 cm for a craft strip
        anomaly_pairs = re.findall(r"(\d+)\s*(സെ\.?മീ\.?|മീ\.?)", story)
        for val, unit in anomaly_pairs:
            num = int(val)
            if num > 100 and unit.startswith("സെ"):
                issues.append(f"Measurement anomaly: {num} {unit} (implausible for craft item)")
            elif num > 20 and unit.startswith("മീ"):
                issues.append(f"Measurement anomaly: {num} {unit} (too large for classroom)")

        # 10. Character utilization — named characters used only once
        known_char_names = {"അനു", "മീര", "രാഹുൽ", "രാഹുല്", "റാഹുൽ"}
        para_char_appearances: dict[str, int] = {}
        for para in story.split("\n\n"):
            for name in known_char_names:
                if name in para:
                    para_char_appearances[name] = para_char_appearances.get(name, 0) + 1
        ignored_once = [c for c, count in para_char_appearances.items() if count == 1]
        if len(ignored_once) >= 1:
            issues.append(f"Introduced character(s) only appear once: {ignored_once}")

        # 11. Generic ending detector
        parts = story.split("**കഥയുടെ പാഠം:**")
        if len(parts) >= 2:
            ending = parts[0].strip().split("\n")[-1] if parts[0].strip() else ""
            generic_pattern = re.compile(
                r"(അഭിമാനിച്ചു|സന്തോഷിച്ചു|വിജയിച്ചു|ആനന്ദം|സന്തോഷം)",
                re.IGNORECASE,
            )
            generic_matches = generic_pattern.findall(ending)
            specific_details = re.findall(
                r"(തയ്‌ച്ചു|നെയ്‌തു|വരച്ചു|ഒട്ടിച്ചു|മടക്കി|കുത്തി|അലങ്കരിച്ചു|പൂര്‍ത്തിയാക്കി|"
                r"മുറിച്ചു|തിരഞ്ഞെടുത്തു|സൃഷ്ടിച്ചു|ശുചിയാക്കി|കാണിച്ചു|സമ്മാനിച്ചു|"
                r"ഉണ്ടാക്കി|തീർത്തു|ചേർത്തു)",
                ending,
            )
            if len(generic_matches) >= 2 and not specific_details:
                issues.append("Generic ending (only happiness/pride words, no specific craft detail)")

        # 12. Story compression — count source events vs story events
        source_sentences = len([s for s in re.split(r'[.!\n]', source) if s.strip() and len(s.strip()) > 3])
        story_paras = len([p for p in story.split("\n\n") if p.strip()])
        story_paras_without_moral = story_paras
        if "**കഥയുടെ പാഠം:**" in story:
            story_paras_without_moral -= 1
        if source_sentences >= 8 and story_paras_without_moral < 6:
            issues.append(f"Story compression: {source_sentences} source steps → {story_paras_without_moral} story paragraphs")

        # 13. Safety hallucination — injury/cut/burn/fall not in source
        safety_verbs = [
            "മുറിഞ്ഞു", "മുറിവ്", "രക്തം", "ചോര", "വെട്ടി", "കുത്തി",
            "പൊള്ളി", "ചുട്ടു", "വീണു", "വീഴ്‌ച്ച", "അടിച്ചു", "ഇടിച്ചു",
            "തല്ലി", "ഞെരിഞ്ഞു", "ഒടിഞ്ഞു", "പൊട്ടി",
        ]
        story_safety = [v for v in safety_verbs if v in story]
        source_safety = [v for v in safety_verbs if v in source]
        for v in story_safety:
            if v not in source_safety:
                issues.append(f"Safety hallucination: '{v}' in story but not in source")

        # 14. Narrative balance — instruction vs narrative sentence ratio
        sentences = [s.strip() for s in re.split(r'[.!\n]', story) if s.strip()]
        total_sentences = len(sentences)
        instruction_markers = [
            "ആദ്യം", "പിന്നീട്", "തുടര്‍ന്ന്", "അവസാനമായി",
            "എടുത്തു", "വച്ചു", "ചെയ്തു",
        ]
        instruction_count = sum(
            1 for s in sentences
            if any(s.startswith(m) for m in instruction_markers)
        )
        if total_sentences >= 6:
            ratio = instruction_count / total_sentences
            if ratio > 0.5:
                issues.append(f"Too procedural: {instruction_count}/{total_sentences} sentences ({ratio:.0%}) start with instruction markers")

        # 15. Missing dialogue/interaction
        has_dialogue = bool(re.search(r'["\u201C\u201D\u2018\u2019]', story))
        if not has_dialogue and story_paras_without_moral >= 4:
            issues.append("No dialogue in story (characters do not speak)")

        # 16. Repetitive sentence starts
        para_starts = []
        for para in story.split("\n\n"):
            first_sentence = para.strip().split("\n")[0] if para.strip() else ""
            if first_sentence:
                start_word = first_sentence.split()[0] if first_sentence.split() else ""
                para_starts.append(start_word)
        if len(para_starts) >= 4:
            repetitive = [w for w in para_starts if w in ("അവൾ", "അവള്‍", "അനു", "അവൻ", "അവന്‍")]
            if len(repetitive) >= len(para_starts) * 0.6:
                issues.append(f"Repetitive starts: {len(repetitive)}/{len(para_starts)} paragraphs start with '{repetitive[0]}'")

        return issues

    def _extract_facts(self, text: str) -> dict[str, set[str]]:
        """Extract concrete facts from source text for validation."""
        facts: dict[str, set[str]] = {
            "measurements": set(),
            "materials": set(),
            "numbers": set(),
        }
        if not text:
            return facts

        measurement_pattern = re.compile(
            r"(\d+)\s*(സെ\.?മീ\.?|മി\.?മീ\.?|മീ\.?|കി\.?മീ\.?|ഗ്രാം|കി\.?ഗ്രാം|മി\.?ലി\.?|ലി\.?|മണിക്കൂര്‍|മിനിറ്റ്|സെക്കന്റ്|എണ്ണം|തവണ|കഷണം|പേജ്|രൂപ|കോല്‍|ഇഞ്ച്)",
            re.IGNORECASE,
        )
        for m in measurement_pattern.finditer(text):
            facts["measurements"].add(m.group(0).strip())

        for n in re.findall(r"\b\d+\b", text):
            facts["numbers"].add(n)

        material_words = [
            "പേപ്പര്‍", "കത്രിക", "പെൻസിൽ", "റബ്ബർ", "സ്കെയിൽ",
            "ഗ്ലൂ", "പശ", "നിറം", "പെയിന്റ്", "ബ്രഷ്",
            "തുണി", "നൂല്‍", "സൂചി", "ബട്ടണ്‍", "സിപ്പ്",
            "മരം", "ഇരുമ്പ്", "പ്ലാസ്റ്റിക്", "ഗ്ലാസ്", "കവര്‍",
            "ചിപ്പ്", "സ്ട്രിപ്പ്", "ബോര്‍ഡര്‍", "ചട്ടം", "റൂള്",
            "കയറ്", "ചോക്ക്", "തേങ്ങ", "വിസിൽ", "വിസി",
        ]
        for w in material_words:
            if w in text:
                facts["materials"].add(w)

        return facts

    def _validate_story_facts(
        self, source_text: str, story: str
    ) -> list[str]:
        """Compare source facts against generated story and return issues."""
        issues: list[str] = []
        source_facts = self._extract_facts(source_text)
        story_facts = self._extract_facts(story)

        for missing in source_facts["measurements"] - story_facts["measurements"]:
            if len(missing) > 5:
                issues.append(f"Missing measurement: {missing}")

        invented_materials = story_facts["materials"] - source_facts["materials"]
        for mat in sorted(invented_materials):
            issues.append(f"Invented material: {mat}")

        return issues

    @staticmethod
    def _postprocess_story(story: str) -> str:
        """Replace exact measurement numbers with vague terms for natural storytelling."""
        # Fix absurd cm values (e.g., 442 cm → 44 cm — likely OCR corruption)
        story = re.sub(
            r"\b(\d{3,})\s*(സെ\.?മീ\.?)",
            lambda m: f"{int(m.group(1)) // 10 or 20} {m.group(2)}" if int(m.group(1)) > 100 else m.group(0),
            story,
        )
        story = re.sub(
            r"\b\d+\s*(?:മീറ്റര്‍|മീ\.?|അടി)\s*(അകലെ|ദൂരത്തില്‍|ദൂരം|അകലത്തില്‍)",
            r"കുറച്ച് \1",
            story,
            flags=re.IGNORECASE,
        )
        story = re.sub(
            r"\b\d+\s*(?:മീറ്റര്‍|മീ\.?|അടി)\b",
            "കുറച്ച്",
            story,
            flags=re.IGNORECASE,
        )
        return story

    def _generate_story_gemini(
        self,
        answer: str,
        question: str | None = None,
        context_docs: list[dict] | None = None,
        student_profile: dict | None = None,
        max_tokens: int = 16384,
        memory_categories: list[str] | None = None,
    ) -> str:
        """Generate story directly via Gemini (used when STORY_PROVIDER=gemini)."""
        cleaned_source = self._strip_curriculum_metadata(answer)
        profile = student_profile or {}
        reading_age = profile.get("reading_age", 12)
        neuro_tags, neuro_guidelines = self._build_neuro_support_guidelines(student_profile)
        all_memories = profile.get("memories", [])
        if memory_categories:
            all_memories = [m for m in all_memories if m.get("category") in memory_categories]
        memories = all_memories

        context_parts = []
        for i, doc in enumerate((context_docs or [])[:3], 1):
            context_parts.append(f"[{i}] {doc.get('source')} p.{doc.get('page')}: {str(doc.get('text') or '')[:200]}")
        context_block = "\n\n".join(context_parts)

        source_facts = self._extract_facts(cleaned_source)
        facts_block = ""
        if source_facts["measurements"]:
            facts_block += "Measurements in source (use only if plot-relevant): " + ", ".join(sorted(source_facts["measurements"])) + "\n"
        if source_facts["materials"]:
            facts_block += "Materials in source (mention only when used by a character): " + ", ".join(sorted(source_facts["materials"])) + "\n"

        source_sentences = len([s for s in re.split(r'[.!\n]', cleaned_source) if s.strip() and len(s.strip()) > 5])
        if source_sentences <= 3:
            target_paras = "18–25"
        elif source_sentences <= 8:
            target_paras = "22–30"
        elif source_sentences <= 15:
            target_paras = "28–35"
        else:
            target_paras = "30–40"

        system_prompt = (
            "You are a Malayalam storyteller for children. You convert curriculum content into real stories.\n\n"
            "CRITICAL RULES — follow every rule in order:\n\n"
            "1. STORY STRUCTURE: Every story MUST have:\n"
            "   - A child protagonist with a name and a clear goal/want\n"
            "   - A small challenge or problem they face (something actually goes wrong)\n"
            "   - Actions they take to overcome it\n"
            "   - A satisfying outcome tied to their actions\n\n"
            "2. WHAT TO NEVER INCLUDE:\n"
            "   - Module numbers, activity numbers, lesson numbers\n"
            "   - Assessment criteria, evaluation, rubrics, scores\n"
            "   - Homework instructions or \"post to group\" directives\n"
            "   - Teacher notes or curriculum metadata\n"
            "   - The word 'വിലയിരുത്തല്‍' or 'Assessment'\n"
            "   - Activity instructions like 'കുട്ടികളെ ജോഡിയാക്കി'\n\n"
            "3. NEVER USE THESE CURRICULUM WORDS IN THE STORY:\n"
            "   - 'പ്രവര്‍ത്തനം' (children do not call their experiences \"activities\")\n"
            "   - 'മണിക്കൂര്‍' with numbers (\"2 മണിക്കൂര്‍ സമയം\" — this is a lesson plan, not a story)\n"
            "   - 'മീറ്റര്‍' / 'അടി' — replace with vague terms like 'കുറച്ച് അകലെ', 'അല്പം ദൂരെ'\n\n"
            "4. NARRATIVE VOICE — convert instructions into events:\n"
            "   BAD: 'കുട്ടികളെ ജോഡിയാക്കി ഓരോ ജോഡിയും പ്രവര്‍ത്തിച്ചു'\n"
            "   GOOD: 'അനുവും മീരയും ഒരു ജോഡിയായി. അവര്‍ ഒന്നിച്ച് പ്രവര്‍ത്തിച്ചു'\n"
            "   BAD: 'ടീച്ചര്‍ തേങ്ങ, ചോക്ക്, വിസി എന്നിവ നല്‍കി. കുട്ടികള്‍ അവ എടുത്തു.'\n"
            "   GOOD: 'തേങ്ങ കണ്ടപ്പോള്‍ മീരയ്ക്ക് സന്തോഷമായി. അവള്‍ അതെടുത്ത് ഉരുട്ടി.'\n"
            "   BAD: '6 മീറ്റര്‍ അകലെയായി രണ്ട് വൃത്തങ്ങള്‍ വരച്ചു'\n"
            "   GOOD: 'കുറച്ച് അകലെയായി രണ്ട് വൃത്തങ്ങള്‍ വരച്ചു'\n\n"
            "5. EVERY NAMED CHARACTER MUST MATTER:\n"
            "   - If you introduce രാഹുൽ or മീര, they must speak or help.\n"
            "   - Never name a character and then forget them.\n"
            "   - Side characters should react, encourage, or participate.\n\n"
            "6. SHOW EMOTION AFTER A PROBLEM:\n"
            "   BAD: 'തേങ്ങ നിലത്തു വീണു. അവള്‍ അതെടുത്തു.' (no feeling, instant fix)\n"
            "   GOOD: '\"അയ്യോ!\" എന്ന് അനു ഞെട്ടി. രാഹുൽ പറഞ്ഞു, \"പരവായില്ല, വീണ്ടും ശ്രമിക്കൂ!\" അനു ധൈര്യമായി വീണ്ടും തേങ്ങ എടുത്തു.'\n"
            "   After something goes wrong, ALWAYS add the character's feeling (ഞെട്ടി, ഭയപ്പെട്ടു, ദേഷ്യപ്പെട്ടു, നിരാശപ്പെട്ടു) before showing the fix.\n\n"
            "7. NEVER WRITE PROCEDURAL STEPS:\n"
            "   BAD: 'ആദ്യത്തെ കുട്ടി അടുത്ത വൃത്തത്തിലേക്ക് വച്ചു. വരിയുടെ അവസാനത്തില്‍ എത്തി.'\n"
            "   GOOD: 'അനു ഓടി അടുത്ത വൃത്തത്തിലെത്തി. അവള്‍ ആവേശത്തോടെ ഫിനിഷ് ചെയ്തു.'\n\n"
            "8. MATERIALS: Only mention a material if a character uses it in the action. "
            "Never list materials like a supply checklist.\n\n"
            "9. TRUTH: Every fact, measurement, and material MUST come from the source. "
            "NEVER invent numbers, measurements, or materials.\n"
            "   - If source has '44 സെ.മീ.' write '44 സെ.മീ.' — do NOT merge adjacent numbers.\n"
            "   - Source '44 × 2 cm' means 44 cm and 2 cm, NEVER '442 cm'.\n"
            "   - Absurd measurements like 442 cm for a craft strip are IMPOSSIBLE. Use the correct values from source.\n\n"
            "10. PROCESS DETAIL — do NOT compress steps:\n"
            "   - For craft/art activities, describe each step in detail.\n"
            "   - Include: choosing materials, measuring, cutting, arranging, checking alignment, gluing, waiting, adjusting, finishing.\n"
            "   - Show the character making decisions: 'ഏത് നിറം തിരഞ്ഞെടുക്കണം?'\n"
            "   - Show observations: 'ഇത് വളരെ നീളമുണ്ട്', 'ഇത് ചെറുതായി പോയി'\n"
            "   - BAD: 'സ്ട്രിപ്പ് മുറിച്ചു. നെയ്തു. ഒട്ടിച്ചു. കഴിഞ്ഞു.'\n"
            "   - GOOD: 'ആദ്യം അനു നിറങ്ങള്‍ നോക്കി. പച്ചയും മഞ്ഞയും എടുത്തു. പിന്നീട് അവള്‍ കത്രിക കൊണ്ട് സ്ട്രിപ്പ് മുറിച്ചു. \"ഇത് കൃത്യമായ വലുപ്പമാണോ?\" എന്ന് അവള്‍ പരിശോധിച്ചു. തുടര്‍ന്ന് അവള്‍ അവ നെയ്യാന്‍ തുടങ്ങി...'\n\n"
            "11. SAFETY — NEVER invent injuries or accidents:\n"
            "   - Do NOT add cuts, burns, falls, or injuries unless the source mentions them.\n"
            "   - BAD: 'അവളുടെ വിരൽ ചെറുതായി മുറിഞ്ഞു' (not in source!)\n"
            "   - GOOD: Find a non-safety conflict like a measurement being wrong or a piece not fitting.\n"
            "   - For sharp tools, add adult supervision — do NOT let a child get hurt.\n\n"
            "12. FORMAT: Pure narrative. No headings, bullet points, numbered lists, bold text. "
            "The only exception is the final '**കഥയുടെ പാഠം:**' paragraph.\n"
            "13. Paragraphs separated by a blank line. Simple, short sentences in Malayalam.\n"
            "14. Vary sentence structure — do NOT start every paragraph with 'അവൾ' or 'അനു'.\n"
            "15. Include at least one line of dialogue in quotation marks: \"...\"\n"
            "16. Return ONLY the story text, nothing else."
        )

        user_prompt = (
            f"This is the cleaned source material (all truth comes from here):\n{cleaned_source}\n\n"
            f"(Optional) Question: {question or ''}\n"
            f"Context excerpts:\n{context_block}\n\n"
            f"Reading age: {reading_age}\n"
            f"Neuro profile: {neuro_tags}\n"
            f"Neurodivergent support guidelines:\n{neuro_guidelines}\n\n"
            f"Student's personal memories (weave relevant ones into the story naturally):\n{self._format_memories_for_prompt(memories)}\n\n"
            f"Student's personal details (use names/places naturally in the story):\n{self._format_personal_details(profile)}\n\n"
            f"Source facts:\n{facts_block}\n\n"
            "Task:\n"
            f"- Write a {target_paras} paragraph Malayalam story about a child doing the activities described.\n"
            "- Every paragraph separated by a blank line.\n"
            "- The protagonist wants something, tries, faces a small REAL problem, and succeeds.\n"
            "- SHOW THE PROCESS IN DETAIL: For craft activities, describe choosing materials, measuring, cutting, "
            "arranging, checking, assembling — step by step. Do NOT skip steps.\n"
            "- SAFETY: Never invent injuries (cuts, burns, falls). Sharp tools→adult supervision.\n"
            "- Include at least one line of dialogue in \"...\" quotation marks.\n"
            "- Vary paragraph starters — don't start every paragraph with 'അവൾ' or 'അനു'.\n"
            "- Measurements from the facts above — only include them if they matter to the plot.\n"
            "- Materials from the facts above — only mention them when a character actually touches or uses them.\n"
            "- NEVER mention module numbers, assessment, evaluation, homework, or activity codes.\n"
            "- NEVER use the word 'പ്രവര്‍ത്തനം' in the story.\n"
            "- End with '**കഥയുടെ പാഠം:**' and a moral tied to THIS specific story, not a generic one.\n"
            "- Return ONLY the story.\n\n"
            "Story in Malayalam:"
        )

        primary_model = _gemini_model()
        models_to_try = [primary_model] + [m for m in self.STORY_FALLBACK_MODELS if m != primary_model]

        last_error = None
        for model_name in models_to_try:
            print(f"   Trying Gemini model: {model_name}")
            try:
                text = self._call_gemini(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    model=model_name,
                )
                if text:
                    text = self._postprocess_story(text)
                    issues = self._validate_story_facts(cleaned_source, text)
                    quality_issues = self._validate_story_quality(cleaned_source, text)
                    all_issues = issues + quality_issues
                    if all_issues:
                        print(f"   [Story Validation] {len(all_issues)} issue(s): {all_issues[:5]}")
                    return text
            except Exception as exc:
                err_str = str(exc)
                print(f"   Gemini model {model_name} failed: {err_str[:100]}")
                last_error = exc
                if "429" not in err_str and "quota" not in err_str.lower():
                    break

        print(f"   All Gemini models exhausted: {last_error}")
        return "കഥ സൃഷ്ടിക്കാൻ തകരാറ്. മാപ്പ്, പിന്നീട് വീണ്ടും ശ്രമിക്കുക."

    def generate_story_from_answer(
        self,
        answer: str,
        question: str | None = None,
        context_docs: list[dict] | None = None,
        student_profile: dict | None = None,
        story_style: str = "child_friendly",
        max_tokens: int = 16384,
        memory_categories: list[str] | None = None,
    ) -> str:
        """Convert an existing answer/explanation into a short story.

        First strips curriculum metadata, then generates a narrative story
        with proper character goal, conflict, action, and outcome.
        """
        return self._generate_story_gemini(
            answer=answer, question=question, context_docs=context_docs,
            student_profile=student_profile, max_tokens=max_tokens,
            memory_categories=memory_categories,
        )

    def extract_memory_metadata(self, text: str) -> dict:
        """Extract structured metadata from a memory text using Gemini.

        Returns dict with keys: title, summary, category, emotions, people,
        places, activities, tags, importance_score.
        """
        system_prompt = (
            "You are a memory analyzer. Given a student's personal memory text, "
            "extract structured metadata. Return ONLY valid JSON with these keys:\n"
            "  \"title\": a short title (max 80 chars),\n"
            "  \"summary\": one-sentence summary,\n"
            "  \"category\": one of PERSONAL, FAMILY, ACHIEVEMENT, EXPERIENCE, PREFERENCE,\n"
            "  \"emotions\": array of emotion words (e.g. [\"happy\",\"nostalgic\"]),\n"
            "  \"people\": array of person names mentioned,\n"
            "  \"places\": array of place names mentioned,\n"
            "  \"activities\": array of activities described,\n"
            "  \"tags\": array of 2-5 keyword tags,\n"
            "  \"importance_score\": integer 1-5 (5 = most significant life event).\n\n"
            "Category definitions:\n"
            "- PERSONAL: identity, feelings, daily life\n"
            "- FAMILY: family members, activities with family\n"
            "- ACHIEVEMENT: success, award, skill learned, goal reached\n"
            "- EXPERIENCE: specific event or activity (trip, festival, visit)\n"
            "- PREFERENCE: likes, dislikes, favorites, wishes\n\n"
            "If no people/places/emotions are mentioned, use empty arrays [].\n"
            "Output ONLY the raw JSON, no markdown fences, no extra text."
        )
        print(f"  [Memory] Extracting metadata from: {text[:80]}...")
        try:
            response = self._call_gemini(system_prompt=system_prompt, user_prompt=text, max_tokens=1024, temperature=0.1)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[-1]
                response = response.rsplit("```", 1)[0]
            data = json.loads(response)
            assert isinstance(data, dict), "Response must be a dict"
            data.setdefault("title", "")
            data.setdefault("summary", "")
            data.setdefault("category", "PERSONAL")
            data.setdefault("emotions", [])
            data.setdefault("people", [])
            data.setdefault("places", [])
            data.setdefault("activities", [])
            data.setdefault("tags", [])
            data.setdefault("importance_score", 3)
            if data["category"] not in ("PERSONAL", "FAMILY", "ACHIEVEMENT", "EXPERIENCE", "PREFERENCE"):
                data["category"] = "PERSONAL"
            data["importance_score"] = max(1, min(5, int(data.get("importance_score", 3))))
            print(f"  [Memory] Metadata: title={data['title'][:50]}, category={data['category']}")
            return data
        except Exception as exc:
            print(f"  [Memory] Metadata extraction failed: {exc}, using defaults")
            return {"title": "", "summary": "", "category": "PERSONAL",
                    "emotions": [], "people": [], "places": [],
                    "activities": [], "tags": [], "importance_score": 3}

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Transcribe audio using Gemini's inline audio support."""
        import base64
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{_gemini_model()}:generateContent?key={self.gemini_api_key}"
        b64 = base64.b64encode(audio_bytes).decode("utf-8")
        payload = {
            "contents": [{
                "parts": [
                    {"inlineData": {"mimeType": mime_type, "data": b64}},
                    {"text": "Transcribe this audio exactly as spoken. Output only the transcription, nothing else."},
                ]
            }],
            "generationConfig": {"maxOutputTokens": 16384, "temperature": 0.1},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=120)
        body = json.loads(resp.read())
        candidates = body.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        raise RuntimeError("Gemini audio transcription returned empty result")

    def _format_memories_for_prompt(self, memories: list[dict]) -> str:
        """Format memories list into a prompt-friendly string for story generation."""
        if not memories:
            return "(no memories yet)"
        lines = []
        for m in memories[:5]:
            cat = m.get("category", "PERSONAL")
            text = m.get("text", "")
            title = m.get("title") or ""
            if title:
                lines.append(f"- [{cat}] {title}: {text}")
            else:
                lines.append(f"- [{cat}] {text}")
        return "\n".join(lines)

    @staticmethod
    def _format_personal_details(profile: dict) -> str:
        """Format student personal details for story prompt injection."""
        parts = []
        for key, label in [
            ("father_name", "Father's name"),
            ("mother_name", "Mother's name"),
            ("grandfather_name", "Grandfather's name"),
            ("grandmother_name", "Grandmother's name"),
            ("favorite_color", "Favorite color"),
            ("teacher_name", "Teacher's name"),
            ("place", "Place/hometown"),
            ("friends", "Friends' names"),
        ]:
            val = profile.get(key)
            if val:
                parts.append(f"{label}: {val}")
        if not parts:
            return "(no personal details yet)"
        return "\n".join(parts)

