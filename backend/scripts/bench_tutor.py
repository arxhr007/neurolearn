"""Benchmark script for NeuroLearn tutor endpoints.

Run inside the project's virtualenv (myenv):

    source myenv/bin/activate
    python3 scripts/bench_tutor.py --base-url http://localhost:8000 --iterations 5

The script logs in as teacher/student, then issues repeated `/api/tutor/question`
requests and optional `/api/tutor/answer` follow-ups, measuring latencies.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4


def _request_json(method: str, url: str, data: dict | None = None, headers: dict | None = None, timeout: int | float = 60) -> dict:
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


def bench(args) -> int:
    base = args.base_url.rstrip("/")

    print("health:")
    h = _request_json("GET", f"{base}/api/health", timeout=args.timeout)
    print(json.dumps(h, indent=2))

    # Login as admin to provision teacher/student if needed
    admin = _request_json(
        "POST",
        f"{base}/api/auth/login",
        data={"email": args.admin_email, "password": args.admin_password, "role": "admin"},
        timeout=args.timeout,
    )
    admin_token = admin.get("access_token")
    if not admin_token:
        print("Admin login failed")
        return 1
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    if not args.skip_provision:
        # ensure teacher
        teachers = _request_json("GET", f"{base}/api/admin/teachers", headers=admin_headers, timeout=args.timeout)
        trows = teachers.get("teachers", []) if isinstance(teachers, dict) else []
        if not any(t.get("username") == args.teacher_username for t in trows):
            _request_json(
                "POST",
                f"{base}/api/admin/teachers",
                data={"username": args.teacher_username, "password": args.teacher_password, "full_name": args.teacher_full_name},
                headers=admin_headers,
                timeout=args.timeout,
            )

    # teacher login
    teacher = _request_json(
        "POST",
        f"{base}/api/auth/login",
        data={"email": args.teacher_username, "password": args.teacher_password, "role": "teacher"},
        timeout=args.timeout,
    )
    teacher_token = teacher.get("access_token")
    if not teacher_token:
        print("Teacher login failed")
        return 1
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    if not args.skip_provision:
        # ensure student
        students = _request_json("GET", f"{base}/api/teacher/students", headers=teacher_headers, timeout=args.timeout)
        srows = students.get("students", []) if isinstance(students, dict) else []
        if not any(s.get("student_id") == args.student_id for s in srows):
            _request_json(
                "POST",
                f"{base}/api/teacher/students",
                data={
                    "student_id": args.student_id,
                    "username": args.student_username,
                    "password": args.student_password,
                    "full_name": args.student_name,
                    "age": 10,
                },
                headers=teacher_headers,
                timeout=args.timeout,
            )

    # student login
    student = _request_json(
        "POST",
        f"{base}/api/auth/login",
        data={"email": args.student_username, "password": args.student_password, "role": "student"},
        timeout=args.timeout,
    )
    student_token = student.get("access_token")
    if not student_token:
        print("Student login failed")
        return 1
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # warmup
    print("Warmup round")
    conv_id = args.conversation_id or str(uuid4())
    _request_json(
        "POST",
        f"{base}/api/tutor/question",
        data={"student_id": args.student_id, "conversation_id": conv_id, "question": args.question, "context": {}},
        headers=student_headers,
        timeout=args.timeout,
    )

    q_times = []
    a_times = []
    for i in range(args.iterations):
        print(f"Iter {i+1}/{args.iterations}")
        start_q = time.perf_counter()
        q = _request_json(
            "POST",
            f"{base}/api/tutor/question",
            data={"student_id": args.student_id, "conversation_id": conv_id, "question": args.question, "context": {}},
            headers=student_headers,
            timeout=args.timeout,
        )
        elapsed_q = (time.perf_counter() - start_q) * 1000.0
        q_times.append(elapsed_q)
        print(f"  question: {elapsed_q:.1f} ms, check_question={bool(q.get('check_question'))}")
        node_timings = (q.get("raw_state") or {}).get("node_timings") or q.get("node_timings")
        if node_timings:
            print("    node_timings:")
            for t in node_timings:
                print(f"      {t.get('node')}: {t.get('elapsed_ms'):.1f} ms")

        if q.get("check_question"):
            start_a = time.perf_counter()
            a = _request_json(
                "POST",
                f"{base}/api/tutor/answer",
                data={
                    "student_id": args.student_id,
                    "conversation_id": q.get("conversation_id"),
                    "turn_id": q.get("turn_id"),
                    "student_answer": args.check_answer,
                    "check_answer_hint": q.get("check_answer_hint"),
                },
                headers=student_headers,
                timeout=args.timeout,
            )
            elapsed_a = (time.perf_counter() - start_a) * 1000.0
            a_times.append(elapsed_a)
            print(f"  answer: {elapsed_a:.1f} ms, is_correct={a.get('is_correct')}")
            node_timings = (a.get("raw_state") or {}).get("node_timings") or a.get("node_timings")
            if node_timings:
                print("    node_timings:")
                for t in node_timings:
                    print(f"      {t.get('node')}: {t.get('elapsed_ms'):.1f} ms")

    def stats(name, arr):
        if not arr:
            return {}
        return {
            "count": len(arr),
            "mean_ms": statistics.mean(arr),
            "median_ms": statistics.median(arr),
            "min_ms": min(arr),
            "max_ms": max(arr),
        }

    summary = {"question": stats("question", q_times), "answer": stats("answer", a_times)}
    print("\nSummary:\n", json.dumps(summary, indent=2))

    return 0


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--iterations", type=int, default=5)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--admin-email", default="admin")
    p.add_argument("--admin-password", default="admin")
    p.add_argument("--teacher-username", default="teacher1")
    p.add_argument("--teacher-password", default="teacher123")
    p.add_argument("--teacher-full-name", default="Teacher User")
    p.add_argument("--student-id", default="s100")
    p.add_argument("--student-username", default="student1")
    p.add_argument("--student-password", default="student123")
    p.add_argument("--student-name", default="Test Student")
    p.add_argument("--skip-provision", action="store_true")
    p.add_argument("--question", default="Why is handwashing important?")
    p.add_argument("--check-answer", default="Because it prevents germs.")
    p.add_argument("--conversation-id", default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(bench(args))
