"""Shared text normalization helpers for OCR and indexing."""

import re

_RE_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_RE_PAGE_NUMBER = re.compile(
    r"(?m)^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$"
)
_RE_HEADER_FOOTER = re.compile(
    r"(?m)^.{0,60}(പേജ്|page|PAGE|അധ്യായം|chapter|CHAPTER)\s*\d*.*$",
    re.IGNORECASE,
)


def normalize_ocr_text(raw: str) -> str:
    """Normalize OCR text into a cleaned single-line representation."""
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\n", "\n").replace("\\r", "\n")
    text = text.replace("\u00a0", " ")
    text = _RE_PAGE_NUMBER.sub("", text)
    text = _RE_HEADER_FOOTER.sub("", text)
    text = re.sub(r"\s+", " ", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    return text.strip()
