import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.users.models import UserRole
from app.users.schemas import UserOut, clean_name

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def validate_password_strength(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    if value != value.strip():
        raise ValueError("Password must not start or end with whitespace")
    return value


class _PasswordConfirmation(BaseModel):
    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class SignupRequest(_PasswordConfirmation):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    confirm_password: str
    role: UserRole = UserRole.WAREHOUSE_STAFF

    _clean_name = field_validator("name")(clean_name)
    _strong_password = field_validator("password")(validate_password_strength)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{4,10}$")


class VerifyOtpResponse(BaseModel):
    reset_token: str
    expires_in: int = Field(description="Reset token lifetime in seconds")


class ResetPasswordRequest(_PasswordConfirmation):
    reset_token: str = Field(min_length=1)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    confirm_password: str

    _strong_password = field_validator("password")(validate_password_strength)


class MessageResponse(BaseModel):
    message: str
