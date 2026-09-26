import itertools

import pytest

from tests.conftest import auth_headers, login, signup


def _headers_for(client, email: str, role: str) -> dict[str, str]:
    assert signup(client, email=email, role=role).status_code == 201
    return auth_headers(login(client, email=email).json()["access_token"])


@pytest.fixture
def manager(client):
    return _headers_for(client, "manager@example.com", "INVENTORY_MANAGER")


@pytest.fixture
def staff(client):
    return _headers_for(client, "staff@example.com", "WAREHOUSE_STAFF")


def field_errors(response) -> dict[str, str]:
    """Map FastAPI-style error details to {field: message}."""
    detail = response.json()["detail"]
    assert isinstance(detail, list), detail
    return {str(item["loc"][-1]): item["msg"] for item in detail}


class MasterData:
    """Creates master-data records through the API as an inventory manager."""

    def __init__(self, client, headers):
        self.client = client
        self.headers = headers
        self._seq = itertools.count(1)

    def post(self, path: str, **payload):
        return self.client.post(f"/api{path}", json=payload, headers=self.headers)

    def _create(self, path: str, payload: dict) -> dict:
        response = self.post(path, **payload)
        assert response.status_code == 201, response.text
        return response.json()

    def category(self, **overrides) -> dict:
        return self._create("/categories", {"name": f"Category {next(self._seq)}", **overrides})

    def unit(self, **overrides) -> dict:
        n = next(self._seq)
        return self._create("/units", {"name": f"Unit {n}", "symbol": f"u{n}", **overrides})

    def warehouse(self, **overrides) -> dict:
        n = next(self._seq)
        return self._create("/warehouses", {"name": f"Warehouse {n}", "code": f"WH{n}", **overrides})

    def location(self, warehouse_id: int | None = None, **overrides) -> dict:
        n = next(self._seq)
        warehouse_id = warehouse_id or self.warehouse()["id"]
        return self._create(
            "/locations", {"warehouse_id": warehouse_id, "name": f"Rack {n}", "code": f"R{n}", **overrides}
        )

    def product(self, **overrides) -> dict:
        n = next(self._seq)
        payload = {"name": f"Product {n}", "sku": f"SKU-{n}", **overrides}
        payload.setdefault("category_id", self.category()["id"])
        payload.setdefault("unit_of_measure_id", self.unit()["id"])
        return self._create("/products", payload)

    def rule(self, **overrides) -> dict:
        payload = {"minimum_quantity": 5, "target_quantity": 20, **overrides}
        payload.setdefault("product_id", self.product()["id"])
        payload.setdefault("location_id", self.location()["id"])
        return self._create("/reorder-rules", payload)


@pytest.fixture
def md(client, manager):
    return MasterData(client, manager)
