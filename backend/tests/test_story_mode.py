import pytest

from langgraph_app.services.tutor_service import TutorService, TutorServiceConfig


class DummyLLM:
    def generate_story_from_answer(self, answer, question=None, context_docs=None, student_profile=None, story_style=None):
        return f"STORY: {answer[:30]}"


class DummyStudentDB:
    def get_student_profile(self, student_id):
        return {"student_id": student_id, "reading_age": 10, "neuro_profile": ["general"]}


def test_generate_story_from_state_basic():
    llm = DummyLLM()
    student_db = DummyStudentDB()
    svc = TutorService(graph=object(), retriever=object(), student_db=student_db, llm=llm, config=TutorServiceConfig())

    state = {"answer": "This is a sample answer explaining handwashing step by step.", "question": "Why wash hands?", "docs": []}
    story = svc.generate_story_from_state(state, student_id="s-test")
    assert story.startswith("STORY:"), "Expected story helper to be used"
