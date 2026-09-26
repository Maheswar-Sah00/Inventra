from datetime import timedelta

from sqlalchemy import select

from app.auth.models import PasswordResetOTP
from app.core.database import utcnow
from app.users.models import User
from tests.conftest import PASSWORD, auth_headers, login

NEW_PASSWORD = "BrandNew456"
GENERIC_MESSAGE = "If an account exists for this email, a verification code has been sent."


def request_otp(client, email="asha@example.com"):
    return client.post("/api/auth/forgot-password", json={"email": email})


def verify(client, otp, email="asha@example.com"):
    return client.post("/api/auth/verify-otp", json={"email": email, "otp": otp})


def reset(client, reset_token, password=NEW_PASSWORD, confirm=None):
    return client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "password": password, "confirm_password": confirm or password},
    )


def wrong_code(otp: str) -> str:
    return "".join(str((int(c) + 1) % 10) for c in otp)


def test_otp_is_generated_and_stored_hashed(client, user, email_sender, db, settings):
    response = request_otp(client, email="ASHA@example.com")
    assert response.status_code == 202
    assert response.json()["message"] == GENERIC_MESSAGE

    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "asha@example.com"
    otp = email_sender.last_otp()
    assert len(otp) == settings.OTP_LENGTH and otp.isdigit()

    record = db.scalar(select(PasswordResetOTP))
    assert record.user_id == user["id"]
    assert otp not in record.otp_hash
    assert record.verified_at is None and record.consumed_at is None


def test_unknown_email_gets_identical_response_and_no_email(client, email_sender):
    response = request_otp(client, email="nobody@example.com")
    assert response.status_code == 202
    assert response.json()["message"] == GENERIC_MESSAGE
    assert email_sender.sent == []


def test_full_reset_flow_changes_password(client, user, email_sender):
    request_otp(client)
    verified = verify(client, email_sender.last_otp())
    assert verified.status_code == 200
    reset_token = verified.json()["reset_token"]

    response = reset(client, reset_token)
    assert response.status_code == 200

    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_invalid_otp_is_rejected_and_counted(client, user, email_sender, db):
    request_otp(client)
    response = verify(client, wrong_code(email_sender.last_otp()))
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification code"
    assert db.scalar(select(PasswordResetOTP)).attempts == 1


def test_otp_for_other_email_is_rejected(client, user, email_sender):
    request_otp(client)
    assert verify(client, email_sender.last_otp(), email="nobody@example.com").status_code == 400


def test_expired_otp_is_rejected(client, user, email_sender, db):
    request_otp(client)
    otp = email_sender.last_otp()
    record = db.scalar(select(PasswordResetOTP))
    record.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert verify(client, otp).status_code == 400


def test_otp_cannot_be_reused(client, user, email_sender):
    request_otp(client)
    otp = email_sender.last_otp()
    first = verify(client, otp)
    assert first.status_code == 200
    # The same code cannot be verified a second time...
    assert verify(client, otp).status_code == 400
    # ...and the reset token it produced works exactly once.
    assert reset(client, first.json()["reset_token"]).status_code == 200
    assert reset(client, first.json()["reset_token"], password="Another789").status_code == 400
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_otp_locks_after_too_many_wrong_attempts(client, user, email_sender, settings):
    request_otp(client)
    otp = email_sender.last_otp()
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert verify(client, wrong_code(otp)).status_code == 400
    # Even the correct code no longer works once locked.
    assert verify(client, otp).status_code == 400


def test_new_otp_invalidates_previous_one(client, user, email_sender):
    request_otp(client)
    first_otp = email_sender.last_otp()
    request_otp(client)
    second_otp = email_sender.last_otp()
    if first_otp != second_otp:
        assert verify(client, first_otp).status_code == 400
    assert verify(client, second_otp).status_code == 200


def test_resend_cooldown_suppresses_repeat_emails(client, user, email_sender, settings, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    assert request_otp(client).status_code == 202
    assert request_otp(client).status_code == 202
    assert len(email_sender.sent) == 1


def test_hourly_otp_cap(client, user, email_sender, settings, monkeypatch):
    monkeypatch.setattr(settings, "OTP_MAX_REQUESTS_PER_HOUR", 2)
    for _ in range(4):
        assert request_otp(client).status_code == 202
    assert len(email_sender.sent) == 2


def test_inactive_user_gets_no_otp(client, user, email_sender, db):
    db.get(User, user["id"]).is_active = False
    db.commit()
    request_otp(client)
    assert email_sender.sent == []


def test_expired_reset_token_is_rejected(client, user, email_sender, db, settings, monkeypatch):
    request_otp(client)
    monkeypatch.setattr(settings, "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", -1)
    reset_token = verify(client, email_sender.last_otp()).json()["reset_token"]
    assert reset(client, reset_token).status_code == 400
    assert login(client, password=PASSWORD).status_code == 200


def test_garbage_reset_token_is_rejected(client, user):
    assert reset(client, "not-a-token").status_code == 400


def test_access_token_cannot_be_used_as_reset_token(client, token):
    assert reset(client, token).status_code == 400


def test_reset_validates_new_password(client, user, email_sender):
    request_otp(client)
    reset_token = verify(client, email_sender.last_otp()).json()["reset_token"]
    assert reset(client, reset_token, password="weak").status_code == 422
    assert reset(client, reset_token, password=NEW_PASSWORD, confirm="Mismatch999").status_code == 422
    # Validation failures do not burn the reset token.
    assert reset(client, reset_token).status_code == 200


def test_reset_signs_out_existing_sessions(client, token, email_sender):
    request_otp(client)
    reset_token = verify(client, email_sender.last_otp()).json()["reset_token"]
    reset(client, reset_token)
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 401


def test_verify_otp_validates_format(client, user):
    assert verify(client, "abc123").status_code == 422
    assert client.post("/api/auth/verify-otp", json={"email": "asha@example.com"}).status_code == 422
