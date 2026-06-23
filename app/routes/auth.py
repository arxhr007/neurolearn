"""Session-based login routes for web pages."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import create_access_token
from app.services.rate_limit import RateLimiter
from app.services.session import clear_session, get_session_user, set_session_user, validate_csrf
from app.services.user_service import (
    authenticate_admin,
    authenticate_student,
    authenticate_teacher,
    sync_student_profile_to_legacy,
)


router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = RateLimiter(max_calls=12, window_seconds=60)


def _rate_limit(request: Request, label: str) -> None:
    key = f"{label}:{request.client.host if request.client else 'unknown'}"
    if not login_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Too many login attempts")


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf(request, csrf_token)
    _rate_limit(request, "admin")
    admin = authenticate_admin(db, username, password)
    if not admin:
        return _redirect("/admin/login?error=invalid")

    set_session_user(
        request,
        {"role": "admin", "user_id": admin.id, "username": admin.username},
    )
    return _redirect("/admin/dashboard")


@router.post("/teacher/login")
async def teacher_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf(request, csrf_token)
    _rate_limit(request, "teacher")
    teacher = authenticate_teacher(db, username, password)
    if not teacher:
        return _redirect("/teacher/login?error=invalid")

    set_session_user(
        request,
        {"role": "teacher", "user_id": teacher.id, "username": teacher.username},
    )
    return _redirect("/teacher/dashboard")


@router.post("/student/login")
async def student_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    validate_csrf(request, csrf_token)
    _rate_limit(request, "student")
    student = authenticate_student(db, username, password)
    if not student:
        return _redirect("/student/login?error=invalid")

    sync_student_profile_to_legacy(student)

    set_session_user(
        request,
        {
            "role": "student",
            "user_id": student.id,
            "username": student.username,
            "student_id": student.student_id,
            "full_name": student.full_name,
            "learning_style": student.learning_style,
            "reading_age": student.reading_age,
            "age": student.age,
            "interests": student.interests,
            "neuro_profile": student.neuro_profile,
            "father_name": student.father_name,
            "mother_name": student.mother_name,
            "grandfather_name": student.grandfather_name,
            "grandmother_name": student.grandmother_name,
            "favorite_color": student.favorite_color,
            "teacher_name": student.teacher_name,
            "place": student.place,
            "friends": student.friends,
            "favorite_food": student.favorite_food,
            "favorite_animal": student.favorite_animal,
            "favorite_interest": student.favorite_interest,
        },
    )
    return _redirect("/student/dashboard")


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    clear_session(request)
    return _redirect("/admin/login")


@router.get("/session-token")
async def session_token(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = create_access_token(
        username=str(user.get("username")),
        role=str(user.get("role")),
        user_id=int(user.get("user_id") or 0),
        student_id=user.get("student_id"),
    )
    return {"access_token": token}
