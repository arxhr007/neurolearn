"""Full-stack FastAPI entrypoint combining API + Jinja pages."""

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from api_main import app
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routes import auth as auth_routes
from app.routes import web as web_routes
from app.services.user_service import ensure_default_admin, ensure_single_admin


settings = get_settings()

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.state.templates = Jinja2Templates(directory=settings.templates_dir)

# Remove the API root route so the web router handles "/"
app.routes[:] = [r for r in app.routes if not (getattr(r, "path", None) == "/" and getattr(r, "methods", None) == {"GET"})]
app.include_router(web_routes.router)
app.include_router(auth_routes.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    with SessionLocal() as db:
        ensure_default_admin(db)
        ensure_single_admin(db)
