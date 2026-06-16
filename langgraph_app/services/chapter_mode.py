"""Helpers for opt-in chapter mode built on top of existing chunk files."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import json
import re
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChapterInfo:
    source: str
    file_name: str
    chunk_count: int
    page_count: int
    first_page: int | None
    last_page: int | None


def default_chunks_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "output" / "rag_chunks"


def _resolve_chunks_dir(chunks_dir: str | Path | None = None) -> Path:
    return Path(chunks_dir).expanduser().resolve() if chunks_dir else default_chunks_dir()


def _safe_load_json(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _normalize_source_name(source: str) -> str:
    value = (source or "").strip()
    if value.lower().endswith(".pdf"):
        return value
    if value:
        return f"{value}.pdf"
    return "unknown.pdf"


_TOPIC_STOPWORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "this",
    "that",
    "these",
    "those",
    "into",
    "about",
    "your",
    "their",
    "they",
    "them",
    "there",
    "here",
    "what",
    "when",
    "where",
    "why",
    "how",
    "ഒരു",
    "ഈ",
    "അത്",
    "അവ",
    "ഇത്",
    "എന്ന്",
    "എന്ന",
    "എന്നും",
    "വരെ",
    "കൂടി",
    "നിന്ന്",
    "നിന്നും",
    "ഉണ്ട്",
    "ഉള്ള",
    "ആണ്",
}


def suggest_chapter_topics(chapter_docs: list[dict[str, Any]], max_topics: int = 6) -> list[str]:
    """Extract simple topic suggestions from chapter text.

    The goal is not perfect NLP; it is to surface a short, readable list of
    likely topics so the learner does not have to invent one from scratch.
    """
    if not chapter_docs:
        return []

    unigram_counts: Counter[str] = Counter()
    bigram_counts: Counter[str] = Counter()
    token_pattern = re.compile(r"[A-Za-z\u0D00-\u0D7F]{3,}")

    for doc in chapter_docs:
        text = str(doc.get("text") or "").lower()
        tokens = [token for token in token_pattern.findall(text) if token not in _TOPIC_STOPWORDS]
        if not tokens:
            continue
        unigram_counts.update(tokens)
        bigram_counts.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:]) if left != right)

    suggestions: list[str] = []
    seen: set[str] = set()

    for topic, _ in bigram_counts.most_common(max_topics):
        if topic not in seen:
            seen.add(topic)
            suggestions.append(topic)

    for topic, _ in unigram_counts.most_common(max_topics * 2):
        if topic not in seen:
            seen.add(topic)
            suggestions.append(topic)
        if len(suggestions) >= max_topics:
            break

    return suggestions[:max_topics]


def estimate_chapter_difficulty(topic: str, chapter_docs: list[dict[str, Any]]) -> int:
    """Estimate how much practice/story depth the current topic likely needs.

    The result is a small integer between 1 and 5. Harder or broader topics,
    plus chapters with more material, get a higher score.
    """
    topic_text = (topic or "").strip()
    topic_words = [word for word in re.findall(r"[A-Za-z\u0D00-\u0D7F]+", topic_text) if len(word) > 1]
    doc_count = len(chapter_docs or [])
    avg_length = 0
    if chapter_docs:
        total_text = sum(len(str(doc.get("text") or "")) for doc in chapter_docs)
        avg_length = total_text // max(doc_count, 1)

    score = 1
    if len(topic_words) >= 2:
        score += 1
    if len(topic_words) >= 4:
        score += 1
    if doc_count >= 4:
        score += 1
    if doc_count >= 8 or avg_length >= 250:
        score += 1
    return max(1, min(score, 5))


def plan_chapter_session(topic: str, chapter_docs: list[dict[str, Any]]) -> dict[str, int]:
    """Plan the minimum story segments and drill questions for chapter mode."""
    difficulty = estimate_chapter_difficulty(topic, chapter_docs)
    doc_count = len(chapter_docs or [])
    base = 3

    story_segments = max(base, min(8, base + difficulty - 1 + doc_count // 4))
    question_count = max(base, min(10, base + difficulty - 1 + doc_count // 5))
    return {
        "difficulty": difficulty,
        "story_segments": story_segments,
        "question_count": question_count,
    }


def split_docs_into_segments(chapter_docs: list[dict[str, Any]], segment_count: int) -> list[list[dict[str, Any]]]:
    """Split chapter docs into a small number of contiguous story segments."""
    docs = list(chapter_docs or [])
    if not docs:
        return []
    segment_count = max(1, min(segment_count, len(docs)))
    if segment_count == 1:
        return [docs]

    segments: list[list[dict[str, Any]]] = []
    total = len(docs)
    start = 0
    for index in range(segment_count):
        end = round((index + 1) * total / segment_count)
        if index == segment_count - 1:
            end = total
        segment = docs[start:end]
        if segment:
            segments.append(segment)
        start = end
    return segments or [docs]


def discover_chapters(chunks_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Return chapter-like groups derived from the current chunk JSON files.

    In this codebase, each source PDF acts as a chapter container. This keeps
    chapter mode resilient to changing PDF sets without adding a separate
    chapter manifest.
    """
    root = _resolve_chunks_dir(chunks_dir)
    if not root.exists():
        return []

    chapters: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if path.name == "_manifest.json":
            continue
        chunks = _safe_load_json(path)
        if not chunks:
            continue

        sources = [_normalize_source_name(str(item.get("source") or path.stem)) for item in chunks if isinstance(item, dict)]
        source = sources[0] if sources else _normalize_source_name(path.stem)
        pages = sorted({int(item.get("page")) for item in chunks if isinstance(item, dict) and str(item.get("page") or "").isdigit()})
        if not pages:
            pages = sorted({int(item.get("page")) for item in chunks if isinstance(item, dict) and item.get("page") is not None})

        chapters.append(
            {
                "source": source,
                "file_name": path.name,
                "chunk_count": len(chunks),
                "page_count": len(pages),
                "first_page": pages[0] if pages else None,
                "last_page": pages[-1] if pages else None,
            }
        )

    chapters.sort(key=lambda item: (str(item.get("source") or "").lower(), str(item.get("file_name") or "").lower()))
    return chapters


# ── Module extraction from chunks ───────────────────────────────────

# OCR sometimes renders digit "1" as Devanagari danda (।, U+0964)
_DANDA_FIX = re.compile(
    r"(മൊഡ്യൂള്\u200d|മൊഡ്വ്യൂള്\u200d)\s*[-:]?\s*।"
)

_MODULE_PATTERN = re.compile(
    r"(?:മൊഡ്യൂള്\u200d|മൊഡ്വ്യൂള്\u200d)\s*[-:]?\s*(\d+)\s*:?\s*(.*?)(?=(?:മൊഡ്യൂള്\u200d|മൊഡ്വ്യൂള്\u200d)|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def extract_modules(
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Scan chunks for module (മൊഡ്യൂള്) listings.

    Returns a list of ``{number, title, page, chunk_id}`` dicts sorted by
    page/module number.  The title is cleaned to at most ~80 characters.
    """
    found: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()

    for c in chunks:
        text = str(c.get("text") or "")
        text = _DANDA_FIX.sub(r"\1 1", text)
        for match in _MODULE_PATTERN.finditer(text):
            num = int(match.group(1))
            if num in seen_numbers:
                continue
            seen_numbers.add(num)
            raw_title = match.group(2).strip()
            # Trim at common delimiters that aren't part of the module name
            for delim in ("  ", " മേഖല", " ഉപനൈപുണി", " |", " \\n"):
                idx = raw_title.find(delim)
                if idx > 0:
                    raw_title = raw_title[:idx]
            title = raw_title.strip().replace("\n", " ")[:80]
            found.append({
                "number": num,
                "title": title,
                "page": c.get("page"),
                "chunk_id": c.get("chunk_id"),
            })

    found.sort(key=lambda m: (m["page"] or 0, m["number"]))
    return found


def _find_source_json(
    chapter_source: str,
    chunks_dir: str | Path | None = None,
) -> Path | None:
    """Locate the JSON chunk file for *chapter_source*."""
    root = _resolve_chunks_dir(chunks_dir)
    target = _normalize_source_name(chapter_source)
    candidates = [
        root / f"{Path(target).stem}.json",
        root / f"{Path(chapter_source).stem}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    if root.exists():
        for p in sorted(root.glob("*.json")):
            if p.name == "_manifest.json":
                continue
            data = _safe_load_json(p)
            if not data:
                continue
            first = _normalize_source_name(str(data[0].get("source") or p.stem))
            if first == target:
                return p
    return None


def load_module_docs(
    chapter_source: str,
    module_number: int,
    chunks_dir: str | Path | None = None,
    max_docs: int = 8,
) -> list[dict[str, Any]]:
    """Load up to *max_docs* chunk dicts that belong to *module_number*.

    Strategy:
    1. For each module, find the page where it appears with the *fewest* other
       distinct module references — that page is the module's content start.
       (TOC/detail pages have many refs; content headers have few or one.)
    2. The content range spans [start_page, next_module's_start_page).
    3. Cover/intro/about pages (before the first detectable module header) are
       automatically excluded.
    """
    chosen_path = _find_source_json(chapter_source, chunks_dir)
    if chosen_path is None:
        return []

    all_chunks = [item for item in _safe_load_json(chosen_path) if isinstance(item, dict)]
    all_chunks.sort(key=lambda item: (int(item.get("page") or 0), int(item.get("chunk_id") or 0)))

    # Per page: how many distinct modules are referenced
    per_page_refs: dict[int, set[int]] = {}
    # Per module: pages where it appears
    module_pages: dict[int, list[int]] = {}
    for c in all_chunks:
        p = int(c.get("page") or 0)
        text = str(c.get("text") or "")
        text = _DANDA_FIX.sub(r"\1 1", text)
        for m in _MODULE_PATTERN.finditer(text):
            num = int(m.group(1))
            per_page_refs.setdefault(p, set()).add(num)
            module_pages.setdefault(num, []).append(p)

    if not module_pages or module_number not in module_pages:
        return [] if module_number > 1 else all_chunks[:max_docs]

    # For this module: pick the page with the FEWEST other module refs
    pages_for_module = sorted(set(module_pages[module_number]))
    page_ref_counts = [(p, len(per_page_refs.get(p, set()))) for p in pages_for_module]
    min_count = min(c for _, c in page_ref_counts)
    start_page = min(p for p, c in page_ref_counts if c == min_count)

    # Find next higher module's start page as boundary
    next_starts: list[int] = []
    for num in sorted(module_pages.keys()):
        if num <= module_number:
            continue
        np = sorted(set(module_pages[num]))
        np_counts = [(p, len(per_page_refs.get(p, set()))) for p in np]
        nm = min(c for _, c in np_counts)
        ns = min(p for p, c in np_counts if c == nm)
        if ns > start_page:
            next_starts.append(ns)
    end_page = min(next_starts) if next_starts else 9999

    filtered = [
        c for c in all_chunks
        if start_page <= (int(c.get("page") or 0)) < end_page
    ]
    docs = filtered[:max_docs] if filtered else all_chunks[:max_docs]

    return [
        {
            "text": str(item.get("text") or ""),
            "source": _normalize_source_name(str(item.get("source") or chosen_path.stem)),
            "page": item.get("page"),
            "chunk_id": item.get("chunk_id"),
            "vector_id": f"{chosen_path.stem}__p{item.get('page')}_c{item.get('chunk_id')}",
        }
        for item in docs
    ]


def load_chapter_docs(
    chapter_source: str,
    chunks_dir: str | Path | None = None,
    max_docs: int = 8,
) -> list[dict[str, Any]]:
    """Load representative docs for a chapter/source PDF.

    Returns a small set of chunk dicts sorted by page/chunk_id so the LLM can
    ground chapter-mode drill questions in the actual PDF content.
    """
    root = _resolve_chunks_dir(chunks_dir)
    target = _normalize_source_name(chapter_source)
    candidate_paths = [root / f"{Path(target).stem}.json", root / f"{Path(chapter_source).stem}.json"]

    chosen_path: Path | None = None
    for path in candidate_paths:
        if path.exists():
            chosen_path = path
            break

    if chosen_path is None and root.exists():
        for path in sorted(root.glob("*.json")):
            if path.name == "_manifest.json":
                continue
            chunks = _safe_load_json(path)
            if not chunks:
                continue
            first_source = _normalize_source_name(str(chunks[0].get("source") or path.stem))
            if first_source == target:
                chosen_path = path
                break

    if chosen_path is None:
        return []

    chunks = [item for item in _safe_load_json(chosen_path) if isinstance(item, dict)]
    chunks.sort(key=lambda item: (int(item.get("page") or 0), int(item.get("chunk_id") or 0)))

    docs: list[dict[str, Any]] = []
    for item in chunks[:max_docs]:
        docs.append(
            {
                "text": str(item.get("text") or ""),
                "source": _normalize_source_name(str(item.get("source") or chosen_path.stem)),
                "page": item.get("page"),
                "chunk_id": item.get("chunk_id"),
                "vector_id": f"{chosen_path.stem}__p{item.get('page')}_c{item.get('chunk_id')}",
            }
        )
    return docs
