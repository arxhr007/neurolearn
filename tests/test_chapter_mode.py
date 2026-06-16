from __future__ import annotations

import json

from langgraph_app.services.chapter_mode import discover_chapters, load_chapter_docs, suggest_chapter_topics
from langgraph_app.services.tutor_service import TutorService, TutorServiceConfig


class DummyRetriever:
    def health_check(self):
        return True

    def get_stats(self):
        return {"chunks": 0}


class DummyStudentDB:
    def get_active_learning_goal(self, student_id):
        return None

    def get_student_profile(self, student_id):
        return {"student_id": student_id, "reading_age": 10, "neuro_profile": ["general"]}

    def health_check(self):
        return True


class DummyLLM:
    def generate_chapter_drill_bundle(
        self,
        chapter_name,
        topic,
        chapter_docs=None,
        student_profile=None,
        question_index=1,
        total_questions=3,
        previous_questions=None,
        review_focus=None,
    ):
        return {"question": f"{chapter_name} Q{question_index}", "expected_answer": topic}


def test_discover_and_load_chapters(tmp_path):
    chunks_dir = tmp_path / "rag_chunks"
    chunks_dir.mkdir()
    chunk_file = chunks_dir / "Sample Chapter.pdf.json"
    chunk_file.write_text(
        json.dumps(
            [
                {"source": "Sample Chapter.pdf", "page": 1, "chunk_id": 1, "text": "First page text."},
                {"source": "Sample Chapter.pdf", "page": 2, "chunk_id": 2, "text": "Second page text."},
            ]
        ),
        encoding="utf-8",
    )

    chapters = discover_chapters(chunks_dir)
    assert chapters
    assert chapters[0]["source"] == "Sample Chapter.pdf"
    assert chapters[0]["chunk_count"] == 2

    docs = load_chapter_docs("Sample Chapter.pdf", chunks_dir)
    assert len(docs) == 2
    assert docs[0]["source"] == "Sample Chapter.pdf"


def test_tutor_service_delegates_chapter_drill_generation():
    service = TutorService(
        graph=object(),
        retriever=DummyRetriever(),
        student_db=DummyStudentDB(),
        llm=DummyLLM(),
        config=TutorServiceConfig(),
    )

    bundle = service.generate_chapter_drill_bundle(
        chapter_name="Sample Chapter.pdf",
        topic="hygiene",
        chapter_docs=[{"source": "Sample Chapter.pdf", "page": 1, "text": "Wash hands."}],
        student_profile={"reading_age": 10},
        question_index=1,
        total_questions=3,
        previous_questions=[],
    )

    assert bundle["question"] == "Sample Chapter.pdf Q1"
    assert bundle["expected_answer"] == "hygiene"


def test_suggest_chapter_topics_lists_readable_topics():
    docs = [
        {"text": "Hand washing keeps hygiene strong and prevents disease."},
        {"text": "Good hygiene and clean hands protect children and families."},
    ]

    topics = suggest_chapter_topics(docs, max_topics=4)

    assert topics
    assert any("hygiene" in topic for topic in topics)
    assert any("hand" in topic or "hands" in topic for topic in topics)
