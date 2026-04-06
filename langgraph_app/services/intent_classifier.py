"""LLM-based intent classifier with deterministic fallback."""

import re

from groq import Groq

from langgraph_app.config import INTENT_MODEL
from langgraph_app.services.intent_rules import classify_intent


class IntentClassifier:
    def __init__(self, groq_client: Groq):
        self.client = groq_client

    def classify(self, question: str) -> str:
        label, _ = self.classify_with_source(question)
        return label

    def classify_with_source(self, question: str) -> tuple[str, str]:
        fallback_intent = classify_intent(question)

        def _normalize_label(raw: str) -> str | None:
            text = (raw or "").strip().lower()
            if not text:
                return None

            # Direct exact labels.
            if text in ("new_concept", "answer"):
                return text

            # Tolerate minor formatting variations from the model.
            compact = re.sub(r"[^a-z_]", "", text)
            if compact in ("new_concept", "newconcept", "newconceptrequest"):
                return "new_concept"
            if compact in ("answer", "useranswer", "response"):
                return "answer"

            # Malayalam cues if model replies in Malayalam instead of labels.
            if any(k in text for k in ("ഉത്തരം", "മറുപടി", "പ്രതികരണം")):
                return "answer"
            if any(k in text for k in ("പുതിയ ആശയം", "വിശദീകരണം", "ചോദ്യം")):
                return "new_concept"

            return None

        system_prompt = (
            "You are an intent classifier for a Malayalam educational tutor. "
            "The user input is usually in Malayalam. "
            "Classify the input into exactly one label: new_concept or answer. "
            "Return only the label with no punctuation or explanation."
        )
        user_prompt = (
            "Rules:\n"
            "- new_concept: learner asks for explanation/definition/how/why/what in Malayalam or English.\n"
            "- answer: learner is responding to a previously asked check question with an attempt.\n"
            "Examples:\n"
            "Input: 'പഠന രീതി എന്താണ്?' -> new_concept\n"
            "Input: 'എന്റെ ഉത്തരം: സഹകരണം പ്രധാനമാണ്' -> answer\n"
            "Input: 'ഞാൻ കരുതുന്നത് സഹകരണം ടീമിന് സഹായിക്കും.' -> answer\n"
            "Input: 'എനിക്ക് തോന്നുന്നത് പങ്കുവെക്കൽ സാമൂഹിക കഴിവ് വളർത്തും.' -> answer\n"
            "Input:\n"
            f"{question}\n\n"
            "Output label:"
        )

        try:
            response = self.client.chat.completions.create(
                model=INTENT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=32,
            )
            raw_label = response.choices[0].message.content or ""
            label = _normalize_label(raw_label)
            if label:
                return label, "llm"

            # Retry once with a stricter correction prompt if first output is not parseable.
            retry_prompt = (
                "Return ONLY one token from this set: new_concept, answer.\n"
                "Do not include explanations, punctuation, or extra words.\n"
                "Input:\n"
                f"{question}\n\n"
                "Label:"
            )
            retry = self.client.chat.completions.create(
                model=INTENT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": retry_prompt},
                ],
                temperature=0.0,
                max_tokens=8,
            )
            retry_raw = retry.choices[0].message.content or ""
            retry_label = _normalize_label(retry_raw)
            if retry_label:
                return retry_label, "llm"

            return fallback_intent, "rule_fallback_parse"
        except Exception:
            return fallback_intent, "rule_fallback_error"
