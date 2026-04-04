"""Rule-based fallback intent classification."""

import re

_ANSWER_HINTS = (
    "answer",
    "answered",
    "reply",
    "respond",
    "i think",
    "ഉത്തരം",
    "എന്റെ ഉത്തരം",
    "ഞാൻ കരുതുന്നു",
    "ഞാൻ കരുതുന്നത്",
    "എനിക്ക് തോന്നുന്നു",
    "എനിക്ക് തോന്നുന്നത്",
    "അതെ",
    "അല്ല",
    "ഇതാണ്",
    "ആണ്",
    "സഹായിക്കും",
)

_NEW_CONCEPT_HINTS = (
    "എന്ത്",
    "എന്താണ്",
    "എങ്ങനെ",
    "എന്തുകൊണ്ട്",
    "വിശദീകരിക്ക",
    "നിർവചിക്ക",
    "അർത്ഥം",
    "വ്യത്യാസം",
)


def classify_intent(question: str) -> str:
    """Classify as 'new_concept' or 'answer' using deterministic rules."""
    text = question.strip().lower()

    if not text:
        return "new_concept"

    # If the learner is asserting an answer/opinion, prioritize answer intent.
    if any(hint in text for hint in _ANSWER_HINTS):
        return "answer"

    if re.search(r"\b(why|how|what|explain|define|meaning|difference)\b", text):
        return "new_concept"

    if any(hint in text for hint in _NEW_CONCEPT_HINTS):
        return "new_concept"

    if "?" in text:
        # Question mark is a strong signal for concept/explanation requests.
        return "new_concept"

    return "new_concept"
