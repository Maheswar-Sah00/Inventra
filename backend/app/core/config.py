"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "change-me-in-env-this-is-not-a-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "StockSense API"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    API_PREFIX: str = "/api"

    DATABASE_URL: str = "postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense"

    # Comma-separated list of allowed browser origins.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    JWT_SECRET: str = INSECURE_DEFAULT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_REQUESTS_PER_HOUR: int = 5
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 10

    # Roles a user may pick for themselves at signup (comma-separated).
    SIGNUP_ALLOWED_ROLES: Annotated[list[str], NoDecode] = ["INVENTORY_MANAGER", "WAREHOUSE_STAFF"]

    # Per-client-IP request limit for sensitive auth endpoints (login, signup, OTP).
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20

    # "console" prints emails to the server log (development only); "smtp" sends real mail.
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    EMAIL_HOST: str = ""
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM: str = "StockSense <no-reply@stocksense.local>"
    EMAIL_USE_TLS: bool = True

    @field_validator("CORS_ORIGINS", "SIGNUP_ALLOWED_ROLES", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET == INSECURE_DEFAULT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters in production")
            if self.EMAIL_BACKEND == "console":
                raise ValueError("EMAIL_BACKEND=console is development-only; configure SMTP in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
