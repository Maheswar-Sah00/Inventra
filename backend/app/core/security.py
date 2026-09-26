"""Password hashing and JWT helpers. Built on established libraries (pwdlib/Argon2, PyJWT)."""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()  # Argon2id
# Used to keep login timing similar whether or not the account exists.
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(16))

ACCESS_TOKEN_TYPE = "access"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"


class TokenError(Exception):
    """Raised when a token is missing, malformed, expired or of the wrong type."""


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def create_token(subject: str, token_type: str, expires_minutes: int, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "jti": uuid.uuid4().hex,
        **(extra or {}),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload


def generate_otp(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def hash_otp(otp: str) -> str:
    """Keyed hash so a leaked OTP table cannot be brute-forced offline without the server secret."""
    key = get_settings().JWT_SECRET.encode()
    return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()


def otp_matches(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), otp_hash)
