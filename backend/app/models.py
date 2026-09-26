"""Import every module's ORM models here so Alembic sees the full schema.

When you add models in your own module, add one import line below.
"""

from app.auth.models import PasswordResetOTP  # noqa: F401
from app.categories.models import Category  # noqa: F401
from app.core.database import Base  # noqa: F401
from app.locations.models import Location  # noqa: F401
from app.products.models import Product  # noqa: F401
from app.reorder_rules.models import ReorderRule  # noqa: F401
from app.units.models import UnitOfMeasure  # noqa: F401
from app.users.models import User, UserRole  # noqa: F401
from app.warehouses.models import Warehouse  # noqa: F401
