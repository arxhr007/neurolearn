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

_SMALLTALK_HINTS = (
    "hi",
    "hello",
    "hey",
    "hiya",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "whats up",
    "what's up",
    "thanks",
    "thank you",
    "thankyou",
    "ok",
    "okay",
    "bye",
    "goodbye",
)

_SMALLTALK_ML_HINTS = (
    "ഹായ്",
    "ഹലോ",
    "നമസ്കാരം",
    "വന്ദനം",
    "സുഖമാണോ",
    "നന്ദി",
    "ശരി",
    "ഓകെ",
    "ഒകെ",
    "വിട",
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

    if any(hint in text for hint in _SMALLTALK_HINTS):
        return "smalltalk"

    if any(hint in question for hint in _SMALLTALK_ML_HINTS):
        return "smalltalk"

    if re.search(r"\bh+e+l+o+\b", text) or re.search(r"\bh+i+\b", text) or re.search(r"\bh+e+y+\b", text):
        return "smalltalk"

    if re.search(r"\b(why|how|what|explain|define|meaning|difference)\b", text):
        return "new_concept"

    if any(hint in text for hint in _NEW_CONCEPT_HINTS):
        return "new_concept"

    if "?" in text:
        # Question mark is a strong signal for concept/explanation requests.
        return "new_concept"

    return "new_concept"
