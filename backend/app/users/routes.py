from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.users import services
from app.users.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_my_profile(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch("/me", response_model=UserOut)
def update_my_profile(payload: UserUpdate, current_user: CurrentUser, db: Session = Depends(get_db)) -> UserOut:
    return UserOut.model_validate(services.update_profile(db, current_user, payload))
