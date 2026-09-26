"""Reusable authentication/authorization dependencies for every StockSense module.

Usage in another module's router:

    from fastapi import Depends
    from app.auth.dependencies import CurrentUser, require_roles
    from app.users.models import UserRole

    @router.get("/products")
    def list_products(current_user: CurrentUser): ...           # any signed-in, active user

    @router.post("/products", dependencies=[Depends(require_roles(UserRole.INVENTORY_MANAGER))])
    def create_product(...): ...                                 # managers only
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.users.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /api/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Return the authenticated, active user or raise 401 (bad/missing token) / 403 (inactive)."""
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        payload = security.decode_token(credentials.credentials, security.ACCESS_TOKEN_TYPE)
        user_id = int(payload["sub"])
    except (security.TokenError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired token") from None

    user = db.get(User, user_id)
    if user is None or payload.get("ver") != user.token_version:
        raise _unauthorized("Invalid or expired token")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Dependency factory: allow only users whose role is one of `roles`, otherwise 403."""
    allowed = set(roles)

    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to do this")
        return current_user

    return dependency
