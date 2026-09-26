"""Authentication business logic: signup, login, logout and OTP password reset."""

from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.models import PasswordResetOTP
from app.auth.schemas import SignupRequest
from app.core import security
from app.core.config import get_settings
from app.core.database import as_utc, utcnow
from app.users.models import User
from app.users.services import get_user_by_email, normalize_email


class AuthError(Exception):
    """Base class for expected authentication failures; routes map these to HTTP responses."""


class EmailAlreadyRegistered(AuthError):
    pass


class RoleNotAllowed(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InactiveAccount(AuthError):
    pass


class InvalidOtp(AuthError):
    pass


class InvalidResetToken(AuthError):
    pass


# --- Signup / login / logout -------------------------------------------------------------------


def signup(db: Session, data: SignupRequest) -> User:
    if data.role.value not in get_settings().SIGNUP_ALLOWED_ROLES:
        raise RoleNotAllowed()
    email = normalize_email(data.email)
    if get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegistered()
    user = User(
        name=data.name,
        email=email,
        password_hash=security.hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # verify_password runs a dummy hash when user is None so response timing does not reveal accounts.
    if not security.verify_password(password, user.password_hash if user else None):
        raise InvalidCredentials()
    if not user.is_active:
        raise InactiveAccount()
    return user


def create_access_token(user: User) -> str:
    return security.create_token(
        subject=str(user.id),
        token_type=security.ACCESS_TOKEN_TYPE,
        expires_minutes=get_settings().JWT_EXPIRE_MINUTES,
        extra={"role": user.role.value, "ver": user.token_version},
    )


def logout(db: Session, user: User) -> None:
    """Revoke every access token issued to this user so far."""
    user.token_version += 1
    db.commit()


# --- OTP password reset ------------------------------------------------------------------------


def _active_otp(db: Session, user_id: int) -> PasswordResetOTP | None:
    otp = db.scalar(
        select(PasswordResetOTP)
        .where(
            PasswordResetOTP.user_id == user_id,
            PasswordResetOTP.consumed_at.is_(None),
            PasswordResetOTP.verified_at.is_(None),
        )
        .order_by(PasswordResetOTP.created_at.desc(), PasswordResetOTP.id.desc())
        .limit(1)
    )
    if otp is None or as_utc(otp.expires_at) <= utcnow():
        return None
    return otp


def request_password_reset(db: Session, email: str) -> tuple[str, str, str] | None:
    """Create an OTP for an active account and return the email to send as (to, subject, body).

    Returns None for unknown/inactive accounts and when the resend cooldown or hourly cap applies.
    Callers must respond identically either way so the endpoint does not reveal which emails exist.
    """
    settings = get_settings()
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None

    now = utcnow()
    latest = db.scalar(select(func.max(PasswordResetOTP.created_at)).where(PasswordResetOTP.user_id == user.id))
    if latest is not None and now - as_utc(latest) < timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS):
        return None
    recent_count = db.scalar(
        select(func.count())
        .select_from(PasswordResetOTP)
        .where(PasswordResetOTP.user_id == user.id, PasswordResetOTP.created_at > now - timedelta(hours=1))
    )
    if recent_count >= settings.OTP_MAX_REQUESTS_PER_HOUR:
        return None

    # Only the newest code is ever valid.
    db.execute(
        update(PasswordResetOTP)
        .where(PasswordResetOTP.user_id == user.id, PasswordResetOTP.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = security.generate_otp(settings.OTP_LENGTH)
    db.add(
        PasswordResetOTP(
            user_id=user.id,
            otp_hash=security.hash_otp(code),
            expires_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
            created_at=now,
        )
    )
    db.commit()

    body = (
        f"Hello {user.name},\n\n"
        f"Your StockSense password reset code is: {code}\n\n"
        f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes and can be used once.\n"
        "If you did not request a password reset, you can ignore this email.\n"
    )
    return user.email, "Your StockSense password reset code", body


def verify_otp(db: Session, email: str, code: str) -> str:
    """Check the code and exchange it for a short-lived, single-use password reset token."""
    settings = get_settings()
    user = get_user_by_email(db, email)
    otp = _active_otp(db, user.id) if user is not None and user.is_active else None
    if otp is None:
        raise InvalidOtp()

    if not security.otp_matches(code, otp.otp_hash):
        otp.attempts += 1
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.consumed_at = utcnow()  # lock out this code; the user must request a new one
        db.commit()
        raise InvalidOtp()

    otp.verified_at = utcnow()
    db.commit()
    return security.create_token(
        subject=str(user.id),
        token_type=security.PASSWORD_RESET_TOKEN_TYPE,
        expires_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        extra={"otp_id": otp.id},
    )


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    try:
        payload = security.decode_token(reset_token, security.PASSWORD_RESET_TOKEN_TYPE)
        user_id = int(payload["sub"])
        otp_id = int(payload["otp_id"])
    except (security.TokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidResetToken() from exc

    otp = db.scalar(select(PasswordResetOTP).where(PasswordResetOTP.id == otp_id).with_for_update())
    if otp is None or otp.user_id != user_id or otp.verified_at is None or otp.consumed_at is not None:
        raise InvalidResetToken()
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise InvalidResetToken()

    user.password_hash = security.hash_password(new_password)
    user.token_version += 1  # sign out existing sessions after a password change
    otp.consumed_at = utcnow()
    db.commit()
