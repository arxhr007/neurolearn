from __future__ import annotations

from fastapi.testclient import TestClient

import api_main


class DummyTutorService:
    def list_available_chapters(self):
        return [
            {"source": "Chapter One.pdf", "first_page": 1, "last_page": 4, "chunk_count": 12},
            {"source": "Chapter Two.pdf", "first_page": 5, "last_page": 8, "chunk_count": 9},
        ]


def test_api_chapters_returns_discovered_sources():
    original = api_main.get_tutor_service
    api_main.app.dependency_overrides[api_main.get_tutor_service] = lambda: DummyTutorService()
    try:
        client = TestClient(api_main.app)

        login_response = client.post(
            "/api/auth/login",
            json={"email": "admin@neurolearn.local", "password": "admin123", "role": "admin"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        response = client.get(
            "/api/chapters",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "chapters" in payload
        assert len(payload["chapters"]) == 2
        assert payload["chapters"][0]["source"] == "Chapter One.pdf"
    finally:
        api_main.app.dependency_overrides.clear()
        api_main.get_tutor_service = original
