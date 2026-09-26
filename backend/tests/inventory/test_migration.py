from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
INVENTORY_TABLES = {
    "stock",
    "stock_movements",
    "receipts",
    "receipt_items",
    "deliveries",
    "delivery_items",
    "transfers",
    "transfer_items",
    "adjustments",
    "adjustment_items",
}


def test_inventory_migration_upgrades_and_downgrades(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'inv.db').as_posix()}"
    monkeypatch.chdir(BACKEND_DIR)
    monkeypatch.setattr(get_settings(), "DATABASE_URL", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    engine = create_engine(url)

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert INVENTORY_TABLES <= set(inspector.get_table_names())
    unique = {tuple(u["column_names"]) for u in inspector.get_unique_constraints("stock")}
    assert ("product_id", "location_id") in unique
    assert "ix_stock_movements_reference" in {i["name"] for i in inspector.get_indexes("stock_movements")}

    command.downgrade(config, "0002_master_data")
    tables = set(inspect(engine).get_table_names())
    assert not INVENTORY_TABLES & tables
    assert {"products", "locations", "users"} <= tables
    engine.dispose()
