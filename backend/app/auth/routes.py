from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import services
from app.auth.dependencies import CurrentUser
from app.auth.email import EmailSender, get_email_sender
from app.auth.rate_limit import rate_limit
from app.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]

FORGOT_PASSWORD_MESSAGE = "If an account exists for this email, a verification code has been sent."


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("signup"))],
)
def signup(payload: SignupRequest, db: DbSession) -> UserOut:
    try:
        user = services.signup(db, payload)
    except services.EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    except services.RoleNotAllowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This role cannot be chosen at signup") from None
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit("login"))])
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    try:
        user = services.authenticate(db, payload.email, payload.password)
    except services.InvalidCredentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except services.InactiveAccount:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is inactive") from None
    return TokenResponse(
        access_token=services.create_access_token(user),
        expires_in=get_settings().JWT_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: CurrentUser, db: DbSession) -> MessageResponse:
    services.logout(db, current_user)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot-password"))],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> MessageResponse:
    email = services.request_password_reset(db, payload.email)
    if email is not None:
        # Sent after the response so delivery time does not reveal whether the account exists.
        background_tasks.add_task(sender.send, *email)
    return MessageResponse(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/verify-otp", response_model=VerifyOtpResponse, dependencies=[Depends(rate_limit("verify-otp"))])
def verify_otp(payload: VerifyOtpRequest, db: DbSession) -> VerifyOtpResponse:
    try:
        token = services.verify_otp(db, payload.email, payload.otp)
    except services.InvalidOtp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code") from None
    return VerifyOtpResponse(reset_token=token, expires_in=get_settings().PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60)


@router.post(
    "/reset-password", response_model=MessageResponse, dependencies=[Depends(rate_limit("reset-password"))]
)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    try:
        services.reset_password(db, payload.reset_token, payload.password)
    except services.InvalidResetToken:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This reset session has expired or was already used. Please start again."
        ) from None
    return MessageResponse(message="Your password has been reset. You can now sign in.")
