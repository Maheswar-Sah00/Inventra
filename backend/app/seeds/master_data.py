"""DEVELOPMENT/DEMO data: a demo login, one category, two units, one warehouse with two racks.

Run from backend/ after `alembic upgrade head`:

    python -m app.seeds.master_data

Idempotent: rows that already exist (matched by name/code) are left untouched. Refuses to run when
ENVIRONMENT=production. Every record is labelled as demo data so it is easy to spot and remove.
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.core import security
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.locations.models import Location
from app.units.models import UnitOfMeasure
from app.users.models import User, UserRole
from app.warehouses.models import Warehouse

DEMO_NOTE = "Demo data for local development"
# Shown on the login page in development builds (frontend/src/pages/LoginPage.tsx); keep them in sync.
DEMO_EMAIL = "admin@stocksense.com"
DEMO_PASSWORD = "Admin1234"


def _get_or_create(db: Session, model, lookup: dict, defaults: dict | None = None):
    obj = db.scalar(select(model).filter_by(**lookup))
    if obj is not None:
        return obj, False
    obj = model(**lookup, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def seed(db: Session) -> dict[str, int]:
    """Insert missing demo rows and return how many of each kind were created."""
    created = {"users": 0, "categories": 0, "units": 0, "warehouses": 0, "locations": 0}

    _, new = _get_or_create(
        db,
        User,
        {"email": DEMO_EMAIL},
        {
            "name": "Demo Manager",
            "password_hash": security.hash_password(DEMO_PASSWORD),
            "role": UserRole.INVENTORY_MANAGER,
            "is_active": True,
        },
    )
    created["users"] += new

    _, new = _get_or_create(db, Category, {"name": "Raw Materials"}, {"description": DEMO_NOTE})
    created["categories"] += new

    for name, symbol in (("Kilogram", "kg"), ("Piece", "pc")):
        _, new = _get_or_create(db, UnitOfMeasure, {"name": name}, {"symbol": symbol})
        created["units"] += new

    warehouse, new = _get_or_create(db, Warehouse, {"code": "DEMO-MAIN"}, {"name": "Main Warehouse", "address": DEMO_NOTE})
    created["warehouses"] += new

    for name, code in (("Rack A", "RACK-A"), ("Rack B", "RACK-B")):
        _, new = _get_or_create(db, Location, {"warehouse_id": warehouse.id, "code": code}, {"name": name})
        created["locations"] += new

    db.commit()
    return created


def main() -> int:
    if get_settings().ENVIRONMENT == "production":
        print("Refusing to load demo data with ENVIRONMENT=production.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        created = seed(db)
    print("Demo data loaded:", ", ".join(f"{count} {kind}" for kind, count in created.items()), "created")
    print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
