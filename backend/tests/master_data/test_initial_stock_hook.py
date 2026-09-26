"""The contract the inventory module uses to turn a product's initial stock into real stock records."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.products.events import on_initial_stock, remove_initial_stock_handler


@pytest.fixture
def calls():
    received = []

    def handler(db, product, created_by):
        assert product.id is not None  # flushed before handlers run
        received.append(
            {"product_id": product.id, "quantity": product.initial_stock, "location_id": product.initial_location_id, "user": created_by.email}
        )

    on_initial_stock(handler)
    yield received
    remove_initial_stock_handler(handler)


def test_handler_receives_product_with_initial_stock(md, calls):
    location = md.location()
    product = md.product(initial_stock=40, initial_location_id=location["id"])
    assert calls == [
        {"product_id": product["id"], "quantity": Decimal("40"), "location_id": location["id"], "user": "manager@example.com"}
    ]


def test_handler_not_called_without_initial_stock(md, calls):
    md.product()
    md.product(initial_stock=0)
    assert calls == []


def test_handler_not_called_on_update(client, manager, md, calls):
    product = md.product()
    client.patch(f"/api/products/{product['id']}", headers=manager, json={"name": "Renamed"})
    assert calls == []


def test_failing_handler_rolls_back_product_creation(client, manager, md):
    def reject(db, product, created_by):
        raise HTTPException(status_code=409, detail="Inventory could not record the initial stock")

    on_initial_stock(reject)
    try:
        location = md.location()
        response = md.post(
            "/products",
            name="Steel",
            sku="STL-1",
            category_id=md.category()["id"],
            unit_of_measure_id=md.unit()["id"],
            initial_stock=5,
            initial_location_id=location["id"],
        )
    finally:
        remove_initial_stock_handler(reject)

    assert response.status_code == 409
    assert response.json()["detail"] == "Inventory could not record the initial stock"
    assert client.get("/api/products?q=STL-1", headers=manager).json()["total"] == 0
