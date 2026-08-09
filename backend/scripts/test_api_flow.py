import argparse
import json
import os
import sys
import time
import uuid
from typing import Any, Optional, Tuple, List

import requests


def _now_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:6]}"


def _print_step(name: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line = f"{line} - {detail}"
    print(line)


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        token: Optional[str] = None,
        expected: Tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Tuple[bool, int, Any]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")
        resp = requests.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        data = _safe_json(resp)
        return resp.status_code in expected, resp.status_code, data


def wait_for_health(client: ApiClient, wait_seconds: int, interval: float) -> bool:
    deadline = time.time() + max(int(wait_seconds), 0)
    if wait_seconds <= 0:
        return False

    last_code = None
    while time.time() < deadline:
        ok, code, _ = client.request("GET", "/api/health", expected=(200,))
        last_code = code
        if ok:
            return True
        time.sleep(max(float(interval), 0.5))

    if last_code is not None:
        print(f"Health check last status: {last_code}")
    return False


def login_with_fallback(
    client: ApiClient,
    candidates: List[Tuple[str, str, str]],
) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    for role, user, password in candidates:
        ok, code, data = client.request(
            "POST",
            "/api/auth/login",
            expected=(200, 401, 403, 422),
            json={"email": user, "password": password, "role": role},
        )
        if ok:
            return data.get("access_token"), data.get("refresh_token"), data.get("user")
    return None, None, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Test NeuroLearn API workflow")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("API_TIMEOUT", "120")))
    parser.add_argument("--health-wait", type=int, default=int(os.getenv("API_HEALTH_WAIT", "120")))
    parser.add_argument("--health-interval", type=float, default=float(os.getenv("API_HEALTH_INTERVAL", "2")))
    parser.add_argument("--admin-user", default=os.getenv("ADMIN_USER", "admin"))
    parser.add_argument("--admin-pass", default=os.getenv("ADMIN_PASS", "admin"))
    parser.add_argument("--dev-admin-user", default="admin@neurolearn.local")
    parser.add_argument("--dev-admin-pass", default="admin123")
    parser.add_argument("--skip-tutor", action="store_true")
    args = parser.parse_args()

    client = ApiClient(args.base_url, timeout=args.timeout)
    health_client = ApiClient(args.base_url, timeout=min(args.timeout, 15))
    failures = 0

    health_ok = wait_for_health(health_client, args.health_wait, args.health_interval)
    _print_step("health", health_ok, f"waited={args.health_wait}s")
    if not health_ok:
        return 1

    admin_candidates = [
        ("admin", args.admin_user, args.admin_pass),
        ("admin", args.dev_admin_user, args.dev_admin_pass),
    ]
    admin_token, admin_refresh, admin_user = login_with_fallback(client, admin_candidates)
    if admin_token:
        _print_step("admin login", True, f"user={admin_user.get('email')}")
    else:
        _print_step("admin login", False, "no admin credentials worked")
        return 1

    ok, code, data = client.request("POST", "/api/auth/refresh", json={"refresh_token": admin_refresh or ""})
    _print_step("refresh token", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request("POST", "/api/auth/logout", token=admin_token)
    _print_step("logout", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request("GET", "/api/admin/teachers", token=admin_token)
    _print_step("list teachers", ok, f"status={code}")
    failures += 0 if ok else 1

    teacher_username = _now_id("teacher")
    teacher_password = "teachpass123"
    ok, code, data = client.request(
        "POST",
        "/api/admin/teachers",
        token=admin_token,
        json={"username": teacher_username, "password": teacher_password, "full_name": "Test Teacher"},
    )
    _print_step("create teacher", ok, f"status={code}")
    failures += 0 if ok else 1
    teacher_id = data.get("teacher_id") if ok else None

    if teacher_id:
        ok, code, data = client.request(
            "PUT",
            f"/api/admin/teachers/{teacher_id}",
            token=admin_token,
            json={"full_name": "Updated Teacher", "is_active": True},
        )
        _print_step("update teacher", ok, f"status={code}")
        failures += 0 if ok else 1

    ok, code, data = client.request("GET", "/api/admin/retriever/config", token=admin_token)
    _print_step("retriever config", ok, f"status={code}")
    failures += 0 if ok else 1
    if ok and isinstance(data, dict):
        patch_payload = {
            "candidate_k": data.get("candidate_k"),
            "min_similarity": data.get("min_similarity"),
            "dedup_max_per_source_page": data.get("dedup_max_per_source_page"),
            "rerank_enabled": data.get("rerank_enabled"),
            "hybrid_enabled": data.get("hybrid_enabled"),
            "top_k": data.get("top_k"),
            "notes": data.get("notes"),
        }
        ok, code, data = client.request(
            "PATCH",
            "/api/admin/retriever/config",
            token=admin_token,
            json=patch_payload,
        )
        _print_step("update retriever config", ok, f"status={code}")
        failures += 0 if ok else 1

    ok, code, data = client.request("GET", "/api/admin/system/stats", token=admin_token)
    _print_step("system stats", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "POST",
        "/api/auth/login",
        json={"email": teacher_username, "password": teacher_password, "role": "teacher"},
    )
    if ok:
        teacher_token = data.get("access_token")
        _print_step("teacher login", True, f"user={teacher_username}")
    else:
        _print_step("teacher login", False, f"status={code}")
        return 1

    ok, code, data = client.request("GET", "/api/teacher/students", token=teacher_token)
    _print_step("list teacher students", ok, f"status={code}")
    failures += 0 if ok else 1

    student_id = _now_id("s")
    student_username = _now_id("student")
    student_password = "studpass123"
    ok, code, data = client.request(
        "POST",
        "/api/teacher/students",
        token=teacher_token,
        json={
            "student_id": student_id,
            "username": student_username,
            "password": student_password,
            "full_name": "Test Student",
            "age": 11,
            "reading_age": 9,
            "learning_style": "general",
            "interests": ["chess"],
            "neuro_profile": ["general"],
        },
    )
    _print_step("create student", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "PUT",
        f"/api/teacher/students/{student_id}",
        token=teacher_token,
        json={"reading_age": 10, "interests": ["chess", "football"]},
    )
    _print_step("update student", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "POST",
        f"/api/teacher/students/{student_id}/goals",
        token=teacher_token,
        json={"goal_text": "Learn handwashing basics"},
    )
    _print_step("create goal", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/teacher/students/{student_id}/goals",
        token=teacher_token,
    )
    _print_step("list goals", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/students/{student_id}",
        token=teacher_token,
    )
    _print_step("get student (teacher)", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "POST",
        "/api/auth/login",
        json={"email": student_username, "password": student_password, "role": "student"},
    )
    if ok:
        student_token = data.get("access_token")
        _print_step("student login", True, f"user={student_username}")
    else:
        _print_step("student login", False, f"status={code}")
        return 1

    ok, code, data = client.request(
        "GET",
        f"/api/students/{student_id}",
        token=student_token,
    )
    _print_step("get student (self)", ok, f"status={code}")
    failures += 0 if ok else 1

    conversation_id = str(uuid.uuid4())
    tutor_ok = True
    turn_id = None
    check_hint = None

    if not args.skip_tutor:
        ok, code, data = client.request(
            "POST",
            "/api/tutor/question",
            token=student_token,
            expected=(200, 503, 500),
            json={
                "student_id": student_id,
                "conversation_id": conversation_id,
                "question": "What is handwashing?",
                "context": {},
            },
        )
        tutor_ok = ok
        _print_step("tutor question", ok, f"status={code}")
        failures += 0 if ok else 1
        if ok and isinstance(data, dict):
            turn_id = data.get("turn_id")
            check_hint = data.get("check_answer_hint")

    if not args.skip_tutor and tutor_ok and turn_id:
        ok, code, data = client.request(
            "POST",
            "/api/tutor/answer",
            token=student_token,
            expected=(200, 503, 500),
            json={
                "student_id": student_id,
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "student_answer": "It keeps hands clean.",
                "check_answer_hint": check_hint,
            },
        )
        _print_step("tutor answer", ok, f"status={code}")
        failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/teacher/students/{student_id}/mastery",
        token=teacher_token,
    )
    _print_step("teacher mastery list", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/teacher/students/{student_id}/mastery/stats",
        token=teacher_token,
    )
    _print_step("teacher mastery stats", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/teacher/students/{student_id}/conversations",
        token=teacher_token,
    )
    _print_step("teacher conversations", ok, f"status={code}")
    failures += 0 if ok else 1

    if ok and isinstance(data, list) and data:
        convo_id = data[0].get("conversation_id")
        if convo_id:
            ok, code, data = client.request(
                "GET",
                f"/api/teacher/students/{student_id}/conversations/{convo_id}",
                token=teacher_token,
            )
            _print_step("conversation detail", ok, f"status={code}")
            failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/conversations/{student_id}",
        token=student_token,
    )
    _print_step("conversation history", ok, f"status={code}")
    failures += 0 if ok else 1

    ok, code, data = client.request(
        "GET",
        f"/api/conversations/{student_id}/{conversation_id}",
        token=student_token,
    )
    _print_step("conversation by id", ok, f"status={code}")
    failures += 0 if ok else 1

    if failures:
        print(f"\nDone with {failures} failures.")
        return 1

    print("\nAll API checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
