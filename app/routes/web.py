"""Jinja-rendered web pages for each role."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.learning_service import create_goal, list_goals_for_student, list_goals_for_teacher
from app.services.session import get_csrf_token, get_session_user, validate_csrf
from app.services.user_service import create_student, create_teacher, list_students_for_teacher, list_teachers


router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def _render(request: Request, template_name: str, context: dict):
    templates = _templates(request)
    # Starlette's Jinja2Templates expects (request, name, context)
    return templates.TemplateResponse(request, template_name, context)


def _require_role(request: Request, role: str, login_path: str):
    user = get_session_user(request)
    if not user or user.get("role") != role:
        return RedirectResponse(login_path, status_code=303)
    return user


@router.get("/")
async def home():
    return RedirectResponse("/admin/login", status_code=302)


@router.get("/admin/login")
async def admin_login(request: Request, error: str | None = None):
    token = get_csrf_token(request)
    return _render(
        request,
        "admin/login.html",
        {"csrf_token": token, "error": error},
    )


@router.get("/teacher/login")
async def teacher_login(request: Request, error: str | None = None):
    token = get_csrf_token(request)
    return _render(
        request,
        "teacher/login.html",
        {"csrf_token": token, "error": error},
    )


@router.get("/student/login")
async def student_login(request: Request, error: str | None = None):
    token = get_csrf_token(request)
    return _render(
        request,
        "student/login.html",
        {"csrf_token": token, "error": error},
    )


@router.get("/admin/dashboard")
async def admin_dashboard(request: Request):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "admin/dashboard.html",
        {"user": user, "page": "dashboard", "role": "admin", "csrf_token": token},
    )


@router.get("/admin/teachers")
async def admin_teachers(request: Request, created: str | None = None, db: Session = Depends(get_db)):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    teachers = list_teachers(db)
    teacher_rows = [
        {
            "username": teacher.username,
            "full_name": teacher.full_name,
            "is_active": teacher.is_active,
            "student_count": len(teacher.students),
        }
        for teacher in teachers
    ]
    return _render(
        request,
        "admin/teachers.html",
        {
            "user": user,
            "page": "teachers",
            "role": "admin",
            "csrf_token": token,
            "teachers": teacher_rows,
            "created": created == "1",
        },
    )


@router.get("/admin/teachers/create")
async def admin_teachers_create(request: Request):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "admin/teachers_create.html",
        {"user": user, "page": "teachers", "role": "admin", "csrf_token": token},
    )


@router.post("/admin/teachers/create")
async def admin_teachers_create_submit(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    validate_csrf(request, csrf_token)
    try:
        create_teacher(db, username=username, password=password, full_name=full_name)
    except ValueError as exc:
        token = get_csrf_token(request)
        return _render(
            request,
            "admin/teachers_create.html",
            {
                "user": user,
                "page": "teachers",
                "role": "admin",
                "csrf_token": token,
                "error": str(exc),
                "username": username,
                "full_name": full_name,
            },
        )
    return RedirectResponse("/admin/teachers?created=1", status_code=303)


@router.get("/admin/analytics")
async def admin_analytics(request: Request):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "admin/analytics.html",
        {"user": user, "page": "analytics", "role": "admin", "csrf_token": token},
    )


@router.get("/admin/settings")
async def admin_settings(request: Request):
    user = _require_role(request, "admin", "/admin/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "admin/settings.html",
        {"user": user, "page": "settings", "role": "admin", "csrf_token": token},
    )


@router.get("/teacher/dashboard")
async def teacher_dashboard(request: Request):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "teacher/dashboard.html",
        {"user": user, "page": "dashboard", "role": "teacher", "csrf_token": token},
    )


@router.get("/teacher/students")
async def teacher_students(request: Request, created: str | None = None, db: Session = Depends(get_db)):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    teacher_id = int(user.get("user_id") or 0)
    students = list_students_for_teacher(db, teacher_id)
    student_rows = [
        {
            "student_id": student.student_id,
            "username": student.username,
            "is_active": student.is_active,
            "goal_count": len(student.goals),
        }
        for student in students
    ]
    return _render(
        request,
        "teacher/students.html",
        {
            "user": user,
            "page": "students",
            "role": "teacher",
            "csrf_token": token,
            "students": student_rows,
            "created": created == "1",
        },
    )


@router.get("/teacher/students/create")
async def teacher_students_create(request: Request):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "teacher/students_create.html",
        {"user": user, "page": "students", "role": "teacher", "csrf_token": token},
    )


@router.post("/teacher/students/create")
async def teacher_students_create_submit(
    request: Request,
    student_id: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    age: int | None = Form(None),
    reading_age: int | None = Form(None),
    learning_style: str = Form("general"),
    interests: str = Form(""),
    neuro_profile: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    validate_csrf(request, csrf_token)

    def _split_list(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    try:
        create_student(
            db,
            teacher_id=int(user.get("user_id") or 0),
            student_id=student_id,
            username=username,
            password=password,
            full_name=full_name,
            age=age or 10,
            reading_age=reading_age or 8,
            learning_style=learning_style,
            interests=_split_list(interests),
            neuro_profile=_split_list(neuro_profile),
        )
    except ValueError as exc:
        token = get_csrf_token(request)
        return _render(
            request,
            "teacher/students_create.html",
            {
                "user": user,
                "page": "students",
                "role": "teacher",
                "csrf_token": token,
                "error": str(exc),
                "student_id": student_id,
                "username": username,
                "full_name": full_name,
                "age": age,
                "reading_age": reading_age,
                "learning_style": learning_style,
                "interests": interests,
                "neuro_profile": neuro_profile,
            },
        )
    return RedirectResponse("/teacher/students?created=1", status_code=303)


@router.get("/teacher/students/{student_id}")
async def teacher_students_detail(request: Request, student_id: str):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "teacher/students_detail.html",
        {
            "user": user,
            "page": "students",
            "role": "teacher",
            "student_id": student_id,
            "csrf_token": token,
        },
    )


@router.get("/teacher/goals")
async def teacher_goals(request: Request, created: str | None = None, db: Session = Depends(get_db)):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    teacher_id = int(user.get("user_id") or 0)
    students = list_students_for_teacher(db, teacher_id)
    goals = list_goals_for_teacher(db, teacher_id)
    goal_rows = [
        {
            "student_name": goal.student.username,
            "student_id": goal.student.student_id,
            "goal_text": goal.goal_text,
            "is_active": goal.is_active,
        }
        for goal in goals
    ]
    return _render(
        request,
        "teacher/goals.html",
        {
            "user": user,
            "page": "goals",
            "role": "teacher",
            "csrf_token": token,
            "students": students,
            "goals": goal_rows,
            "created": created == "1",
        },
    )


@router.post("/teacher/goals")
async def teacher_goals_create(
    request: Request,
    student_id: int = Form(...),
    goal_text: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    validate_csrf(request, csrf_token)
    try:
        create_goal(db, student_id=student_id, goal_text=goal_text)
    except ValueError as exc:
        token = get_csrf_token(request)
        teacher_id = int(user.get("user_id") or 0)
        students = list_students_for_teacher(db, teacher_id)
        goals = list_goals_for_teacher(db, teacher_id)
        goal_rows = [
            {
                "student_name": goal.student.username,
                "student_id": goal.student.student_id,
                "goal_text": goal.goal_text,
                "is_active": goal.is_active,
            }
            for goal in goals
        ]
        return _render(
            request,
            "teacher/goals.html",
            {
                "user": user,
                "page": "goals",
                "role": "teacher",
                "csrf_token": token,
                "students": students,
                "goals": goal_rows,
                "created": False,
                "error": str(exc),
                "goal_text": goal_text,
                "selected_student_id": student_id,
            },
        )
    return RedirectResponse("/teacher/goals?created=1", status_code=303)


@router.get("/teacher/analytics")
async def teacher_analytics(request: Request):
    user = _require_role(request, "teacher", "/teacher/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "teacher/analytics.html",
        {"user": user, "page": "analytics", "role": "teacher", "csrf_token": token},
    )


@router.get("/student/dashboard")
async def student_dashboard(request: Request):
    user = _require_role(request, "student", "/student/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "student/dashboard.html",
        {"user": user, "page": "dashboard", "role": "student", "csrf_token": token},
    )


@router.get("/student/chat")
async def student_chat(request: Request):
    user = _require_role(request, "student", "/student/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "student/chat.html",
        {"user": user, "page": "chat", "role": "student", "csrf_token": token},
    )


@router.get("/student/goals")
async def student_goals(request: Request, db: Session = Depends(get_db)):
    user = _require_role(request, "student", "/student/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    student_pk = int(user.get("user_id") or 0)
    goals = list_goals_for_student(db, student_pk)
    goal_rows = [
        {
            "goal_text": goal.goal_text,
            "is_active": goal.is_active,
        }
        for goal in goals
    ]
    return _render(
        request,
        "student/goals.html",
        {
            "user": user,
            "page": "goals",
            "role": "student",
            "csrf_token": token,
            "goals": goal_rows,
        },
    )


@router.get("/student/progress")
async def student_progress(request: Request):
    user = _require_role(request, "student", "/student/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "student/progress.html",
        {"user": user, "page": "progress", "role": "student", "csrf_token": token},
    )


@router.get("/student/profile")
async def student_profile(request: Request):
    user = _require_role(request, "student", "/student/login")
    if isinstance(user, RedirectResponse):
        return user
    token = get_csrf_token(request)
    return _render(
        request,
        "student/profile.html",
        {"user": user, "page": "profile", "role": "student", "csrf_token": token},
    )
