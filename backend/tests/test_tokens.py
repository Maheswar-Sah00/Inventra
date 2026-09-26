from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, require_roles
from app.core import security
from app.core.database import get_db
from app.users.models import User, UserRole
from tests.conftest import auth_headers, login, signup


def test_valid_token_grants_access(client, token):
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 200


def test_protected_endpoint_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_token_is_rejected(client, user):
    for bad in ["garbage", "Bearer.also.garbage", security.create_token("1", "access", 5) + "tampered"]:
        response = client.get("/api/auth/me", headers=auth_headers(bad))
        assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, user):
    import jwt

    forged = jwt.encode({"sub": str(user["id"]), "type": "access", "iat": 0, "exp": 9999999999, "ver": 0}, "x" * 40)
    assert client.get("/api/auth/me", headers=auth_headers(forged)).status_code == 401


def test_expired_token_is_rejected(client, user):
    expired = security.create_token(str(user["id"]), security.ACCESS_TOKEN_TYPE, -1, extra={"ver": 0})
    response = client.get("/api/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_password_reset_token_cannot_be_used_as_access_token(client, user):
    reset = security.create_token(str(user["id"]), security.PASSWORD_RESET_TOKEN_TYPE, 5, extra={"ver": 0})
    assert client.get("/api/auth/me", headers=auth_headers(reset)).status_code == 401


def test_token_for_deleted_user_is_rejected(client, token, user, db):
    db.delete(db.get(User, user["id"]))
    db.commit()
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 401


def test_token_of_deactivated_user_is_rejected(client, token, user, db):
    db.scalar(select(User).where(User.id == user["id"])).is_active = False
    db.commit()
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 403


def test_logout_revokes_token(client, token):
    response = client.post("/api/auth/logout", headers=auth_headers(token))
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 401
    assert client.get("/api/users/me", headers=auth_headers(token)).status_code == 401
    # Logging in again issues a fresh, working token.
    new_token = login(client).json()["access_token"]
    assert client.get("/api/auth/me", headers=auth_headers(new_token)).status_code == 200


def test_logout_requires_authentication(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_require_roles_dependency(client, db_session_factory):
    """The contract other modules rely on: CurrentUser and require_roles()."""
    app = FastAPI()

    @app.get("/whoami")
    def whoami(current_user: CurrentUser):
        return {"id": current_user.id, "role": current_user.role, "is_active": current_user.is_active}

    @app.get("/managers-only", dependencies=[Depends(require_roles(UserRole.INVENTORY_MANAGER))])
    def managers_only():
        return {"ok": True}

    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    other = TestClient(app)

    signup(client, email="staff@example.com", role="WAREHOUSE_STAFF")
    signup(client, email="boss@example.com", role="INVENTORY_MANAGER")
    staff = auth_headers(login(client, email="staff@example.com").json()["access_token"])
    boss = auth_headers(login(client, email="boss@example.com").json()["access_token"])

    assert other.get("/whoami", headers=staff).json()["role"] == "WAREHOUSE_STAFF"
    assert other.get("/managers-only", headers=staff).status_code == 403
    assert other.get("/managers-only", headers=boss).status_code == 200
    assert other.get("/managers-only").status_code == 401
