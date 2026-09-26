from app.users.models import User
from tests.conftest import auth_headers


def test_authenticated_user_can_read_own_profile(client, token, user):
    response = client.get("/api/users/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body == user
    assert set(body) == {"id", "name", "email", "role", "is_active", "created_at", "updated_at"}


def test_unauthenticated_user_cannot_read_profile(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.patch("/api/users/me", json={"name": "Hacker"}).status_code == 401


def test_user_can_update_own_name(client, token):
    response = client.patch("/api/users/me", headers=auth_headers(token), json={"name": "  Asha   K  Rao "})
    assert response.status_code == 200
    assert response.json()["name"] == "Asha K Rao"
    assert client.get("/api/users/me", headers=auth_headers(token)).json()["name"] == "Asha K Rao"


def test_profile_update_validation(client, token):
    headers = auth_headers(token)
    assert client.patch("/api/users/me", headers=headers, json={"name": ""}).status_code == 422
    assert client.patch("/api/users/me", headers=headers, json={"name": "A"}).status_code == 422
    assert client.patch("/api/users/me", headers=headers, json={"name": "x" * 101}).status_code == 422
    assert client.patch("/api/users/me", headers=headers, json={}).status_code == 422


def test_role_cannot_be_changed_via_profile(client, token, user, db):
    headers = auth_headers(token)
    for payload in (
        {"name": "Asha", "role": "INVENTORY_MANAGER"},
        {"role": "INVENTORY_MANAGER"},
        {"name": "Asha", "is_active": False},
        {"name": "Asha", "email": "other@example.com"},
    ):
        assert client.patch("/api/users/me", headers=headers, json=payload).status_code == 422

    stored = db.get(User, user["id"])
    assert stored.role.value == "WAREHOUSE_STAFF"
    assert stored.email == "asha@example.com"
    assert stored.is_active is True
