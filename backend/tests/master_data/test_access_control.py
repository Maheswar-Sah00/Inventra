"""Master data sits behind Geeta's auth: any signed-in user reads, only inventory managers write."""

import pytest

RESOURCES = ["/products", "/categories", "/units", "/warehouses", "/locations", "/reorder-rules"]


@pytest.mark.parametrize("path", RESOURCES)
def test_unauthenticated_requests_are_rejected(client, path):
    assert client.get(f"/api{path}").status_code == 401
    assert client.get(f"/api{path}/1").status_code == 401
    assert client.post(f"/api{path}", json={}).status_code == 401
    assert client.patch(f"/api{path}/1", json={}).status_code == 401
    assert client.delete(f"/api{path}/1").status_code == 401


def test_warehouse_staff_can_read_everything(client, staff, md):
    rule = md.rule()
    product = client.get(f"/api/products/{rule['product_id']}", headers=staff).json()
    location = client.get(f"/api/locations/{rule['location_id']}", headers=staff).json()
    for path in RESOURCES:
        assert client.get(f"/api{path}", headers=staff).json()["total"] >= 1
    for path in (
        f"/products/{product['id']}",
        f"/categories/{product['category_id']}",
        f"/units/{product['unit_of_measure_id']}",
        f"/warehouses/{location['warehouse_id']}",
        f"/locations/{location['id']}",
        f"/reorder-rules/{rule['id']}",
    ):
        assert client.get(f"/api{path}", headers=staff).status_code == 200


@pytest.mark.parametrize("path", RESOURCES)
def test_warehouse_staff_cannot_change_master_data(client, staff, md, path):
    rule = md.rule()
    existing = {
        "/products": rule["product_id"],
        "/categories": md.category()["id"],
        "/units": md.unit()["id"],
        "/warehouses": md.warehouse()["id"],
        "/locations": rule["location_id"],
        "/reorder-rules": rule["id"],
    }[path]
    assert client.post(f"/api{path}", headers=staff, json={}).status_code == 403
    assert client.patch(f"/api{path}/{existing}", headers=staff, json={"is_active": False}).status_code == 403
    assert client.delete(f"/api{path}/{existing}", headers=staff).status_code == 403


def test_logged_out_token_is_rejected(client, manager):
    assert client.post("/api/auth/logout", headers=manager).status_code == 200
    assert client.get("/api/products", headers=manager).status_code == 401
