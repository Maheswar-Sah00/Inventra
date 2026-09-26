from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select

from app.categories.models import Category
from app.core.config import get_settings
from app.locations.models import Location
from app.seeds import master_data
from app.units.models import UnitOfMeasure
from app.warehouses.models import Warehouse

BACKEND_DIR = Path(__file__).resolve().parents[2]
MASTER_DATA_TABLES = {"categories", "units_of_measure", "warehouses", "locations", "products", "reorder_rules"}


def test_seed_creates_demo_data_once(db):
    assert master_data.seed(db) == {"users": 1, "categories": 1, "units": 2, "warehouses": 1, "locations": 2}
    assert master_data.seed(db) == {"users": 0, "categories": 0, "units": 0, "warehouses": 0, "locations": 0}

    warehouse = db.scalar(select(Warehouse))
    assert warehouse.name == "Main Warehouse" and "Demo" in warehouse.address
    assert {loc.name for loc in db.scalars(select(Location))} == {"Rack A", "Rack B"}
    assert {u.symbol for u in db.scalars(select(UnitOfMeasure))} == {"kg", "pc"}
    assert db.scalar(select(func.count()).select_from(Category)) == 1


def test_seeded_demo_user_can_log_in(db, client):
    master_data.seed(db)
    response = client.post(
        "/api/auth/login", json={"email": master_data.DEMO_EMAIL, "password": master_data.DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == "INVENTORY_MANAGER"


def test_seed_refuses_to_run_in_production(monkeypatch, capsys):
    monkeypatch.setattr(get_settings(), "ENVIRONMENT", "production")
    assert master_data.main() == 1
    assert "Refusing" in capsys.readouterr().err


def test_master_data_migration_upgrades_and_downgrades(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'md.db').as_posix()}"
    monkeypatch.chdir(BACKEND_DIR)
    monkeypatch.setattr(get_settings(), "DATABASE_URL", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    engine = create_engine(url)

    command.upgrade(config, "head")
    assert MASTER_DATA_TABLES <= set(inspect(engine).get_table_names())
    unique = {tuple(u["column_names"]) for u in inspect(engine).get_unique_constraints("locations")}
    assert {("warehouse_id", "code"), ("warehouse_id", "name")} <= unique

    command.downgrade(config, "0001_auth")
    tables = set(inspect(engine).get_table_names())
    assert not MASTER_DATA_TABLES & tables
    assert "users" in tables
    engine.dispose()
