"""Manage student profiles in SQLite for LangGraph RAG runtime.

Examples:
    python manage_student_db.py add --student-id s1 --learning-style analogy-heavy --reading-age 12 --interests games stories --neuro-profile adhd
  python manage_student_db.py get --student-id s1
  python manage_student_db.py list
    python manage_student_db.py mastery --student-id s1 --limit 20
    python manage_student_db.py set-goal --student-id s1 --goal "Improve hand-washing hygiene understanding"
    python manage_student_db.py active-goal --student-id s1
    python manage_student_db.py goals --student-id s1 --limit 20
"""

import argparse
import json

from langgraph_app.config import STUDENT_DB_PATH
from langgraph_app.services.student_db import StudentDB


ASCII_BANNER = r"""
███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗ ██╗     ███████╗ █████╗ ██████╗ ███╗   ██╗
████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗██║     ██╔════╝██╔══██╗██╔══██╗████╗  ██║
██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║██║     █████╗  ███████║██████╔╝██╔██╗ ██║
██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║██║     ██╔══╝  ██╔══██║██╔══██╗██║╚██╗██║
██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝███████╗███████╗██║  ██║██║  ██║██║ ╚████║
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝

Adaptive AI Tutor for Neurodivergent Learners • V1
"""


def _prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"{label} cannot be empty.")


def _prompt_int(label: str, min_value: int | None = None) -> int:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            value = int(raw)
        except ValueError:
            print(f"{label} must be a number.")
            continue
        if min_value is not None and value < min_value:
            print(f"{label} must be >= {min_value}.")
            continue
        return value


def _prompt_csv(label: str, default: list[str] | None = None) -> list[str]:
    default = default or []
    hint = f" [{', '.join(default)}]" if default else ""
    while True:
        raw = input(f"{label} (comma-separated){hint}: ").strip()
        if not raw and default:
            return default
        items = [item.strip() for item in raw.split(",") if item.strip()]
        if items:
            return items
        print(f"Please enter at least one {label.lower()}.")


def main() -> None:
    print(ASCII_BANNER)
    parser = argparse.ArgumentParser(description="Manage student profiles (SQLite)")
    parser.add_argument(
        "--db-path",
        default=STUDENT_DB_PATH,
        help=f"SQLite DB path (default: {STUDENT_DB_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    add_parser = subparsers.add_parser("add", help="Add or update a student profile")
    add_parser.add_argument("--student-id", required=False, help="Unique student identifier")
    add_parser.add_argument("--name", required=False, help="Student name")
    add_parser.add_argument("--learning-style", required=False, help="Learning style value")
    add_parser.add_argument("--reading-age", required=False, type=int, help="Reading age")
    add_parser.add_argument(
        "--interests",
        nargs="+",
        required=False,
        help="Interest keywords (space-separated)",
    )
    add_parser.add_argument(
        "--neuro-profile",
        nargs="+",
        default=["general"],
        help="Neurodivergent profile tags (e.g., adhd autism dyslexia). Default: general",
    )

    get_parser = subparsers.add_parser("get", help="Fetch one student profile")
    get_parser.add_argument("--student-id", required=True, help="Student identifier")

    subparsers.add_parser("list", help="List all student profiles")

    mastery_parser = subparsers.add_parser("mastery", help="List mastery events for one student")
    mastery_parser.add_argument("--student-id", required=True, help="Student identifier")
    mastery_parser.add_argument("--limit", type=int, default=20, help="Max events to return")

    set_goal_parser = subparsers.add_parser("set-goal", help="Set active learning goal for a student")
    set_goal_parser.add_argument("--student-id", required=True, help="Student identifier")
    set_goal_parser.add_argument("--goal", required=True, help="Learning goal text")

    active_goal_parser = subparsers.add_parser("active-goal", help="Get active learning goal for a student")
    active_goal_parser.add_argument("--student-id", required=True, help="Student identifier")

    goals_parser = subparsers.add_parser("goals", help="List learning goals for a student")
    goals_parser.add_argument("--student-id", required=True, help="Student identifier")
    goals_parser.add_argument("--limit", type=int, default=20, help="Max goals to return")

    args = parser.parse_args()
    if not args.command:
        # Default behavior: launch interactive student profile creation.
        args.command = "add"
    db = StudentDB(args.db_path)

    if args.command == "add":
        # Interactive prompts for any missing fields.
        student_id = (getattr(args, "student_id", None) or "").strip() or _prompt_non_empty("Student ID")
        name = (getattr(args, "name", None) or "").strip() or _prompt_non_empty("Student name")
        learning_style = (getattr(args, "learning_style", None) or "").strip() or _prompt_non_empty("Learning style")
        reading_age_arg = getattr(args, "reading_age", None)
        reading_age = reading_age_arg if reading_age_arg is not None else _prompt_int("Reading age", min_value=1)

        interests = getattr(args, "interests", None)
        if not interests:
            interests = _prompt_csv("Interests")

        neuro_profile_arg = getattr(args, "neuro_profile", None)
        neuro_profile = neuro_profile_arg or ["general"]
        if neuro_profile_arg is None:
            neuro_profile = _prompt_csv("Neuro profile tags", default=["general"])

        db.upsert_student(
            student_id=student_id,
            name=name,
            learning_style=learning_style,
            reading_age=reading_age,
            interest_graph=interests,
            neuro_profile=neuro_profile,
        )
        print(f"Saved student profile: {student_id} ({name})")
        return

    if args.command == "get":
        profile = db.get_student_profile(args.student_id)
        if not profile:
            print(f"Student not found: {args.student_id}")
            return
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return

    if args.command == "list":
        profiles = db.list_students()
        print(json.dumps(profiles, ensure_ascii=False, indent=2))
        return

    if args.command == "mastery":
        events = db.list_mastery_events(args.student_id, limit=args.limit)
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return

    if args.command == "set-goal":
        goal_id = db.set_learning_goal(args.student_id, args.goal)
        print(f"Saved active learning goal for {args.student_id} (goal_id={goal_id})")
        return

    if args.command == "active-goal":
        goal = db.get_active_learning_goal(args.student_id)
        if not goal:
            print(f"No active learning goal for: {args.student_id}")
            return
        print(json.dumps(goal, ensure_ascii=False, indent=2))
        return

    if args.command == "goals":
        goals = db.list_learning_goals(args.student_id, limit=args.limit)
        print(json.dumps(goals, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
