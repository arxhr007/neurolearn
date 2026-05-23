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


def _request_json(method: str, url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
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
    parser.add_argument("--email", default="admin@neurolearn.local", help="Login email")
    parser.add_argument("--password", default="admin123", help="Login password")
    parser.add_argument("--role", default="admin", choices=["student", "teacher", "admin"], help="Login role")
    parser.add_argument("--student-id", default="s100", help="Student id")
    parser.add_argument("--question", default="Why is handwashing important?", help="Tutor question")
    parser.add_argument("--check-answer", default="Because it prevents germs.", help="Answer for check question")
    parser.add_argument("--conversation-id", default=None, help="Conversation id (optional)")
    parser.add_argument("--ensure-student", action="store_true", help="Create/update the student profile before asking")
    parser.add_argument("--student-name", default="Test User", help="Student name")
    parser.add_argument("--learning-style", default="analogy-heavy", help="Learning style")
    parser.add_argument("--reading-age", type=int, default=12, help="Reading age")
    parser.add_argument("--interests", default="chess,football", help="Comma-separated interests")
    parser.add_argument("--neuro-profile", default="adhd,dyslexia", help="Comma-separated neuro tags")
    parser.add_argument("--goal", default=None, help="Optional learning goal to set")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("== Health check ==")
    health = _request_json("GET", f"{base_url}/api/health")
    print(json.dumps(health, indent=2))

    print("\n== Login ==")
    login = _request_json(
        "POST",
        f"{base_url}/api/auth/login",
        data={"email": args.email, "password": args.password, "role": args.role},
    )
    access_token = login.get("access_token")
    if not access_token:
        print("Login failed: no access token")
        return 1

    auth_header = {"Authorization": f"Bearer {access_token}"}

    if args.ensure_student:
        print("\n== Ensure student profile ==")
        interests = _parse_csv(args.interests, ["chess", "football"])
        neuro_profile = _parse_csv(args.neuro_profile, ["general"])
        profile = _request_json(
            "PUT",
            f"{base_url}/api/students/{args.student_id}",
            data={
                "name": args.student_name,
                "learning_style": args.learning_style,
                "reading_age": args.reading_age,
                "interests": interests,
                "neuro_profile": neuro_profile,
            },
            headers=auth_header,
        )
        print(json.dumps(profile, indent=2))

    if args.goal:
        print("\n== Set learning goal ==")
        goal = _request_json(
            "POST",
            f"{base_url}/api/students/{args.student_id}/goals",
            data={"goal_text": args.goal},
            headers=auth_header,
        )
        print(json.dumps(goal, indent=2))

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
        headers=auth_header,
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
            headers=auth_header,
        )
        print(json.dumps(answer, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
