"""Seed the default admin account in the new SQLAlchemy DB."""

from app.database import SessionLocal, init_db
from app.services.user_service import ensure_default_admin


def main() -> None:
    init_db()
    with SessionLocal() as db:
        admin = ensure_default_admin(db)
        print(f"Default admin ready: username={admin.username}")


if __name__ == "__main__":
    main()
