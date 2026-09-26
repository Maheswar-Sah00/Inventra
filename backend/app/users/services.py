from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.models import User
from app.users.schemas import UserUpdate


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    user.name = data.name
    db.commit()
    db.refresh(user)
    return user
