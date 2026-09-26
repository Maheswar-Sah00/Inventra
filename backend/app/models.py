"""Import every module's ORM models here so Alembic sees the full schema.

When you add models in your own module, add one import line below.
"""

from app.auth.models import PasswordResetOTP  # noqa: F401
from app.core.database import Base  # noqa: F401
from app.users.models import User, UserRole  # noqa: F401
