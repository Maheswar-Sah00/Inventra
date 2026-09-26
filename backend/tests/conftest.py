import os
import re

# Configure the app for tests before any app module reads settings.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-1234567890"
os.environ["EMAIL_BACKEND"] = "console"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth.email import get_email_sender  # noqa: E402
from app.auth.rate_limit import reset_rate_limits  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402

PASSWORD = "Secret123"


class FakeEmailSender:
    def __init__(self):
        self.sent: list[dict[str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_otp(self) -> str:
        match = re.search(r"code is: (\d+)", self.sent[-1]["body"])
        assert match, "no OTP found in the last email"
        return match.group(1)


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db(db_session_factory):
    session = db_session_factory()
    yield session
    session.close()


@pytest.fixture
def email_sender():
    return FakeEmailSender()


@pytest.fixture
def settings(monkeypatch):
    """The live settings object; tests may monkeypatch attributes on it."""
    s = get_settings()
    monkeypatch.setattr(s, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    return s


@pytest.fixture
def client(db_session_factory, email_sender, settings):
    app = create_app()

    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_sender] = lambda: email_sender
    reset_rate_limits()
    with TestClient(app) as test_client:
        yield test_client
    reset_rate_limits()


def signup(client, **overrides):
    payload = {
        "name": "Asha Rao",
        "email": "asha@example.com",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "role": "WAREHOUSE_STAFF",
    }
    payload.update(overrides)
    return client.post("/api/auth/signup", json=payload)


def login(client, email="asha@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(client):
    response = signup(client)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def token(client, user):
    response = login(client)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
