"""Real concurrent requests against a file-backed database (separate connections, separate threads).

PostgreSQL relies on the same code path with row locks (SELECT ... FOR UPDATE); SQLite serialises
writers with its database lock. Either way the status compare-and-set plus locked stock check must let
exactly one conflicting validation through.
"""

import threading
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.categories.models import Category
from app.core.security import hash_password
from app.deliveries import services as deliveries
from app.deliveries.schemas import DeliveryCreate
from app.inventory.models import Stock, StockMovement
from app.locations.models import Location
from app.models import Base
from app.products.models import Product
from app.receipts import services as receipts
from app.receipts.schemas import ReceiptCreate
from app.units.models import UnitOfMeasure
from app.users.models import User, UserRole
from app.warehouses.models import Warehouse


@pytest.fixture
def db_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'concurrency.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def ids(db_factory):
    with db_factory() as db:
        user = User(name="Ravi", email="ravi@example.com", password_hash=hash_password("Secret123"), role=UserRole.WAREHOUSE_STAFF)
        warehouse = Warehouse(name="Main", code="MAIN")
        db.add_all([user, warehouse])
        db.flush()
        location = Location(warehouse_id=warehouse.id, name="Rack A", code="A")
        category = Category(name="Furniture")
        unit = UnitOfMeasure(name="Piece", symbol="pc")
        db.add_all([location, category, unit])
        db.flush()
        product = Product(name="Chair", sku="CHR", category_id=category.id, unit_of_measure_id=unit.id)
        db.add(product)
        db.commit()
        return {"user": user.id, "location": location.id, "product": product.id}


def run_concurrently(db_factory, tasks):
    """Run each task(db) in its own thread and session, released at the same moment."""
    barrier = threading.Barrier(len(tasks))
    results = [None] * len(tasks)

    def worker(index, task):
        with db_factory() as db:
            barrier.wait()
            try:
                task(db)
                results[index] = "ok"
            except HTTPException as error:
                results[index] = error.status_code

    threads = [threading.Thread(target=worker, args=(i, t)) for i, t in enumerate(tasks)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results


def receive(db_factory, ids, quantity):
    with db_factory() as db:
        user = db.get(User, ids["user"])
        receipt = receipts.create_receipt(
            db,
            ReceiptCreate(supplier_name="Acme", destination_location_id=ids["location"],
                          items=[{"product_id": ids["product"], "quantity": quantity}]),
            user,
        )
        receipts.validate_receipt(db, receipt, user)
        return receipt.id


def packed_delivery(db_factory, ids, quantity) -> int:
    with db_factory() as db:
        user = db.get(User, ids["user"])
        delivery = deliveries.create_delivery(
            db, DeliveryCreate(source_location_id=ids["location"], items=[{"product_id": ids["product"], "quantity": quantity}]), user
        )
        deliveries.confirm_delivery(db, delivery)
        deliveries.pick_delivery(db, delivery, user)
        deliveries.pack_delivery(db, delivery, user)
        return delivery.id


def stock_and_movements(db_factory, ids):
    with db_factory() as db:
        quantity = db.scalar(select(Stock.quantity).where(Stock.product_id == ids["product"]))
        movements = db.scalar(select(func.count()).select_from(StockMovement))
        return quantity, movements


def validate_delivery_task(ids, delivery_id):
    def task(db):
        deliveries.validate_delivery(db, deliveries.get_delivery(db, delivery_id), db.get(User, ids["user"]))

    return task


def test_concurrent_deliveries_cannot_oversell(db_factory, ids):
    receive(db_factory, ids, 10)
    first = packed_delivery(db_factory, ids, 7)
    second = packed_delivery(db_factory, ids, 6)

    results = run_concurrently(db_factory, [validate_delivery_task(ids, first), validate_delivery_task(ids, second)])

    assert sorted(results, key=str) == [409, "ok"]
    quantity, movements = stock_and_movements(db_factory, ids)
    assert quantity in (Decimal("3"), Decimal("4"))  # 10 - 7 or 10 - 6, never negative
    assert movements == 2  # one receipt + exactly one delivery


def test_concurrent_double_validation_applies_once(db_factory, ids):
    receive(db_factory, ids, 10)
    delivery = packed_delivery(db_factory, ids, 4)

    results = run_concurrently(db_factory, [validate_delivery_task(ids, delivery)] * 4)

    assert results == ["ok"] * 4  # repeats are idempotent successes...
    quantity, movements = stock_and_movements(db_factory, ids)
    assert quantity == Decimal("6")  # ...but stock moved only once
    assert movements == 2


def test_concurrent_receipts_both_apply(db_factory, ids):
    """Two receipts into a position that does not exist yet: both must land, no lost update."""
    with db_factory() as db:
        user = db.get(User, ids["user"])
        receipt_ids = [
            receipts.create_receipt(
                db,
                ReceiptCreate(supplier_name="Acme", destination_location_id=ids["location"],
                              items=[{"product_id": ids["product"], "quantity": q}]),
                user,
            ).id
            for q in (5, 7)
        ]

    def validate(receipt_id):
        def task(db):
            receipts.validate_receipt(db, receipts.get_receipt(db, receipt_id), db.get(User, ids["user"]))

        return task

    assert run_concurrently(db_factory, [validate(r) for r in receipt_ids]) == ["ok", "ok"]
    assert stock_and_movements(db_factory, ids) == (Decimal("12"), 2)
