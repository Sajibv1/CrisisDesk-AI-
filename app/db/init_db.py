from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.admin import AdminUser


def seed_if_needed(session: Session, settings: Settings) -> None:
    existing = session.query(AdminUser).filter(AdminUser.username == settings.admin_username).one_or_none()
    if existing is None:
        session.add(
            AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_active=True,
            )
        )
        session.commit()
