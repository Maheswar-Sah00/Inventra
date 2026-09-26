from types import SimpleNamespace

import pytest

from tests.master_data.conftest import manager, md, staff  # noqa: F401  (re-exported fixtures)


@pytest.fixture
def world(md):
    """Two warehouses, three locations, two products; no stock yet."""
    main = md.warehouse(name="Main Warehouse", code="MAIN")
    second = md.warehouse(name="Second Warehouse", code="WH2")
    category = md.category(name="Raw Materials")
    other_category = md.category(name="Furniture")
    unit = md.unit(name="Piece", symbol="pc")
    return SimpleNamespace(
        main=main,
        second=second,
        rack_a=md.location(warehouse_id=main["id"], name="Rack A", code="RACK-A"),
        rack_b=md.location(warehouse_id=main["id"], name="Rack B", code="RACK-B"),
        rack_c=md.location(warehouse_id=second["id"], name="Rack C", code="RACK-C"),
        steel=md.product(name="Steel Rods", sku="STL", category_id=category["id"], unit_of_measure_id=unit["id"]),
        chair=md.product(name="Chair", sku="CHR", category_id=other_category["id"], unit_of_measure_id=unit["id"]),
        category=category,
        other_category=other_category,
    )


class Inventory:
    """API helpers for inventory tests, acting as warehouse staff (operations are open to all roles)."""

    def __init__(self, client, headers):
        self.client = client
        self.headers = headers

    def post(self, path: str, json: dict | None = None):
        return self.client.post(f"/api{path}", json=json if json is not None else {}, headers=self.headers)

    def get(self, path: str, **params):
        return self.client.get(f"/api{path}", params=params, headers=self.headers)

    def patch(self, path: str, json: dict):
        return self.client.patch(f"/api{path}", json=json, headers=self.headers)

    def create(self, path: str, payload: dict) -> dict:
        response = self.post(path, payload)
        assert response.status_code == 201, response.text
        return response.json()

    def action(self, path: str, expected: int = 200) -> dict:
        response = self.post(path)
        assert response.status_code == expected, response.text
        return response.json()

    def stock(self, product_id: int, location_id: int) -> float:
        items = self.get("/stock", product_id=product_id, location_id=location_id, include_empty=True).json()["items"]
        return items[0]["quantity"] if items else 0

    def movements(self, **filters) -> list[dict]:
        return self.get("/stock-movements", limit=500, **filters).json()["items"]

    def receive(self, product_id: int, location_id: int, quantity, supplier: str = "Acme Metals") -> dict:
        receipt = self.create(
            "/receipts",
            {
                "supplier_name": supplier,
                "destination_location_id": location_id,
                "items": [{"product_id": product_id, "quantity": quantity}],
            },
        )
        return self.action(f"/receipts/{receipt['id']}/validate")

    def delivery(self, location_id: int, lines: list[tuple[int, object]], **extra) -> dict:
        return self.create(
            "/deliveries",
            {
                "source_location_id": location_id,
                "items": [{"product_id": p, "quantity": q} for p, q in lines],
                **extra,
            },
        )

    def prepare_delivery(self, delivery_id: int) -> dict:
        """confirm -> pick -> pack, returning the packed order."""
        confirmed = self.action(f"/deliveries/{delivery_id}/confirm")
        assert confirmed["status"] == "READY", confirmed
        self.action(f"/deliveries/{delivery_id}/pick")
        return self.action(f"/deliveries/{delivery_id}/pack")


@pytest.fixture
def inv(client, staff):
    return Inventory(client, staff)
