import pytest
from sqlalchemy import select

from app.users.models import User
from tests.conftest import PASSWORD, signup


def test_valid_signup_creates_user_with_hashed_password(client, db):
    response = signup(client, email="  New.User@Example.COM ")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["name"] == "Asha Rao"
    assert body["role"] == "WAREHOUSE_STAFF"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body

    stored = db.scalar(select(User).where(User.email == "new.user@example.com"))
    assert stored.password_hash != PASSWORD
    assert stored.password_hash.startswith("$argon2")


def test_signup_as_inventory_manager(client):
    response = signup(client, role="INVENTORY_MANAGER")
    assert response.status_code == 201
    assert response.json()["role"] == "INVENTORY_MANAGER"


def test_signup_defaults_to_warehouse_staff(client):
    payload = {"name": "Ravi", "email": "ravi@example.com", "password": PASSWORD, "confirm_password": PASSWORD}
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "WAREHOUSE_STAFF"


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert signup(client).status_code == 201
    response = signup(client, email="ASHA@example.com")
    assert response.status_code == 409


@pytest.mark.parametrize("email", ["not-an-email", "asha@", "@example.com", ""])
def test_invalid_email_is_rejected(client, email):
    assert signup(client, email=email).status_code == 422


@pytest.mark.parametrize(
    "password",
    ["short1", "allletters", "12345678", " Secret123", "a" * 120 + "1" * 10],
)
def test_weak_or_invalid_password_is_rejected(client, password):
    assert signup(client, password=password, confirm_password=password).status_code == 422


def test_password_confirmation_must_match(client):
    response = signup(client, confirm_password="Different123")
    assert response.status_code == 422
    assert "Passwords do not match" in response.text


@pytest.mark.parametrize("missing", ["name", "email", "password", "confirm_password"])
def test_missing_fields_are_rejected(client, missing):
    payload = {"name": "Asha", "email": "a@example.com", "password": PASSWORD, "confirm_password": PASSWORD}
    del payload[missing]
    assert client.post("/api/auth/signup", json=payload).status_code == 422


def test_blank_name_is_rejected(client):
    assert signup(client, name="   ").status_code == 422


def test_unknown_role_is_rejected(client):
    assert signup(client, role="ADMIN").status_code == 422


def test_cannot_set_privileged_fields_at_signup(client):
    assert signup(client, is_active=False).status_code == 422


def test_role_not_in_signup_allowlist_is_forbidden(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_ALLOWED_ROLES", ["WAREHOUSE_STAFF"])
    assert signup(client, role="INVENTORY_MANAGER").status_code == 403
    assert signup(client, role="WAREHOUSE_STAFF").status_code == 201
