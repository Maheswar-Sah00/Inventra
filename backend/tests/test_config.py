import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_SECRET = "x" * 48


def test_production_rejects_default_or_short_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)  # conftest sets a valid one
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, ENVIRONMENT="production", EMAIL_BACKEND="smtp")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, ENVIRONMENT="production", EMAIL_BACKEND="smtp", JWT_SECRET="short")


def test_production_rejects_console_email_backend():
    with pytest.raises(ValidationError, match="EMAIL_BACKEND"):
        Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET=STRONG_SECRET, EMAIL_BACKEND="console")


def test_production_accepts_safe_settings():
    settings = Settings(_env_file=None, ENVIRONMENT="production", JWT_SECRET=STRONG_SECRET, EMAIL_BACKEND="smtp")
    assert settings.ENVIRONMENT == "production"


def test_comma_separated_lists_are_parsed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("SIGNUP_ALLOWED_ROLES", "WAREHOUSE_STAFF")
    settings = Settings(_env_file=None)
    assert settings.CORS_ORIGINS == ["http://a.test", "http://b.test"]
    assert settings.SIGNUP_ALLOWED_ROLES == ["WAREHOUSE_STAFF"]
