import jwt
from sqlalchemy import select

from app.users.models import User
from tests.conftest import PASSWORD, auth_headers, login


def test_valid_credentials_return_token_and_user(client, user, settings):
    response = login(client, email="ASHA@example.com")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.JWT_EXPIRE_MINUTES * 60
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["role"] == "WAREHOUSE_STAFF"

    claims = jwt.decode(body["access_token"], settings.JWT_SECRET, algorithms=["HS256"])
    assert claims["sub"] == str(user["id"])
    assert claims["type"] == "access"
    assert claims["role"] == "WAREHOUSE_STAFF"

    me = client.get("/api/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]


def test_wrong_password_and_unknown_user_get_the_same_error(client, user):
    wrong_password = login(client, password="Wrong12345")
    unknown_user = login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"detail": "Invalid email or password"}


def test_inactive_user_cannot_log_in(client, user, db):
    db.scalar(select(User).where(User.id == user["id"])).is_active = False
    db.commit()
    response = login(client)
    assert response.status_code == 403
    assert response.json()["detail"] == "This account is inactive"


def test_missing_login_fields_are_rejected(client):
    assert client.post("/api/auth/login", json={"email": "asha@example.com"}).status_code == 422
    assert client.post("/api/auth/login", json={"password": PASSWORD}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": ""}).status_code == 422


def test_login_is_rate_limited(client, user, settings, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", 3)
    for _ in range(3):
        assert login(client, password="Wrong12345").status_code == 401
    response = login(client)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
