"""Simple API smoke test for the NeuroLearn FastAPI backend."""

import argparse
import json
import sys
import urllib.error
import urllib.request
from uuid import uuid4


def _parse_csv(value: str, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


def _request_json(
    method: str,
    url: str,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: int | float = 30,
) -> dict:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {raw}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the NeuroLearn API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", default="admin", help="Admin login identifier")
    parser.add_argument("--password", default="admin", help="Admin password")
    parser.add_argument("--role", default="admin", choices=["student", "teacher", "admin"], help="Login role")
    parser.add_argument("--student-id", default="s100", help="Student id")
    parser.add_argument("--question", default="Why is handwashing important?", help="Tutor question")
    parser.add_argument("--check-answer", default="Because it prevents germs.", help="Answer for check question")
    parser.add_argument("--conversation-id", default=None, help="Conversation id (optional)")
    parser.add_argument("--ensure-student", action="store_true", help="Update the student profile before asking")
    parser.add_argument("--student-name", default="Test User", help="Student name")
    parser.add_argument("--learning-style", default="analogy-heavy", help="Learning style")
    parser.add_argument("--reading-age", type=int, default=12, help="Reading age")
    parser.add_argument("--interests", default="chess,football", help="Comma-separated interests")
    parser.add_argument("--neuro-profile", default="adhd,dyslexia", help="Comma-separated neuro tags")
    parser.add_argument("--student-username", default="student1", help="Student username")
    parser.add_argument("--student-password", default="student123", help="Student password")
    parser.add_argument("--teacher-username", default="teacher1", help="Teacher username")
    parser.add_argument("--teacher-password", default="teacher123", help="Teacher password")
    parser.add_argument("--teacher-full-name", default="Teacher User", help="Teacher full name")
    parser.add_argument("--skip-provision", action="store_true", help="Skip auto-provisioning teacher/student")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    parser.add_argument("--goal", default=None, help="Optional learning goal to set")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("== Health check ==")
    try:
        health = _request_json("GET", f"{base_url}/api/health", timeout=args.timeout)
        print(json.dumps(health, indent=2))
    except Exception as exc:
        print(f"Health check failed: {exc}")

    print("\n== Login ==")
    login = _request_json(
        "POST",
        f"{base_url}/api/auth/login",
        data={"email": args.email, "password": args.password, "role": args.role},
        timeout=args.timeout,
    )
    access_token = login.get("access_token")
    if not access_token:
        print("Login failed: no access token")
        return 1

    admin_header = {"Authorization": f"Bearer {access_token}"}

    teacher_token = None
    student_token = None

    if not args.skip_provision:
        print("\n== Ensure teacher account ==")
        teachers = _request_json(
            "GET",
            f"{base_url}/api/admin/teachers",
            headers=admin_header,
            timeout=args.timeout,
        )
        teacher_rows = teachers.get("teachers", []) if isinstance(teachers, dict) else []
        existing_teacher = next((t for t in teacher_rows if t.get("username") == args.teacher_username), None)
        if existing_teacher:
            print(f"Teacher exists: {args.teacher_username}")
        else:
            created_teacher = _request_json(
                "POST",
                f"{base_url}/api/admin/teachers",
                data={
                    "username": args.teacher_username,
                    "password": args.teacher_password,
                    "full_name": args.teacher_full_name,
                },
                headers=admin_header,
                timeout=args.timeout,
            )
            print(json.dumps(created_teacher, indent=2))

    print("\n== Login (teacher) ==")
    teacher_login = _request_json(
        "POST",
        f"{base_url}/api/auth/login",
        data={"email": args.teacher_username, "password": args.teacher_password, "role": "teacher"},
        timeout=args.timeout,
    )
    teacher_token = teacher_login.get("access_token")
    if not teacher_token:
        print("Teacher login failed: no access token")
        return 1

    teacher_header = {"Authorization": f"Bearer {teacher_token}"}

    if not args.skip_provision:
        print("\n== Ensure student account ==")
        student_list = _request_json(
            "GET",
            f"{base_url}/api/teacher/students",
            headers=teacher_header,
            timeout=args.timeout,
        )
        student_rows = student_list.get("students", []) if isinstance(student_list, dict) else []
        existing_student = next(
            (
                s
                for s in student_rows
                if s.get("student_id") == args.student_id or s.get("username") == args.student_username
            ),
            None,
        )
        if existing_student:
            print(f"Student exists: {args.student_id}")
        else:
            interests = _parse_csv(args.interests, ["chess", "football"])
            neuro_profile = _parse_csv(args.neuro_profile, ["general"])
            created_student = _request_json(
                "POST",
                f"{base_url}/api/teacher/students",
                data={
                    "student_id": args.student_id,
                    "username": args.student_username,
                    "password": args.student_password,
                    "full_name": args.student_name,
                    "age": 10,
                    "reading_age": args.reading_age,
                    "learning_style": args.learning_style,
                    "interests": interests,
                    "neuro_profile": neuro_profile,
                },
                headers=teacher_header,
                timeout=args.timeout,
            )
            print(json.dumps(created_student, indent=2))

    if args.ensure_student:
        print("\n== Ensure student profile ==")
        interests = _parse_csv(args.interests, ["chess", "football"])
        neuro_profile = _parse_csv(args.neuro_profile, ["general"])
        profile = _request_json(
            "PUT",
            f"{base_url}/api/teacher/students/{args.student_id}",
            data={
                "full_name": args.student_name,
                "reading_age": args.reading_age,
                "learning_style": args.learning_style,
                "interests": interests,
                "neuro_profile": neuro_profile,
            },
            headers=teacher_header,
            timeout=args.timeout,
        )
        print(json.dumps(profile, indent=2))

    if args.goal:
        print("\n== Set learning goal ==")
        goal = _request_json(
            "POST",
            f"{base_url}/api/teacher/students/{args.student_id}/goals",
            data={"goal_text": args.goal},
            headers=teacher_header,
            timeout=args.timeout,
        )
        print(json.dumps(goal, indent=2))

    print("\n== Login (student) ==")
    student_login = _request_json(
        "POST",
        f"{base_url}/api/auth/login",
        data={"email": args.student_username, "password": args.student_password, "role": "student"},
        timeout=args.timeout,
    )
    student_token = student_login.get("access_token")
    if not student_token:
        print("Student login failed: no access token")
        return 1

    student_header = {"Authorization": f"Bearer {student_token}"}

    print("\n== Ask tutor question ==")
    conversation_id = args.conversation_id or str(uuid4())
    question = _request_json(
        "POST",
        f"{base_url}/api/tutor/question",
        data={
            "student_id": args.student_id,
            "conversation_id": conversation_id,
            "question": args.question,
            "context": {},
        },
        headers=student_header,
        timeout=args.timeout,
    )
    print(json.dumps(question, indent=2))

    if question.get("check_question"):
        print("\n== Answer check question ==")
        answer = _request_json(
            "POST",
            f"{base_url}/api/tutor/answer",
            data={
                "student_id": args.student_id,
                "conversation_id": question["conversation_id"],
                "turn_id": question["turn_id"],
                "student_answer": args.check_answer,
                "check_answer_hint": question.get("check_answer_hint"),
            },
            headers=student_header,
            timeout=args.timeout,
        )
        print(json.dumps(answer, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
