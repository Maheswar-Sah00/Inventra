import pytest

from tests.master_data.conftest import field_errors


def test_create_warehouse_normalizes_code(md):
    response = md.post("/warehouses", name="Main Warehouse", code=" wh-main ", address=" 12 Industrial Rd ")
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == "WH-MAIN"
    assert body["address"] == "12 Industrial Rd"
    assert body["is_active"] is True


def test_duplicate_warehouse_code_is_rejected(md):
    md.warehouse(name="Main", code="WH1")
    response = md.post("/warehouses", name="Second", code="wh1")
    assert response.status_code == 409
    assert field_errors(response) == {"code": "A warehouse with this code already exists"}


def test_duplicate_warehouse_name_is_rejected(md):
    md.warehouse(name="Main Warehouse", code="WH1")
    response = md.post("/warehouses", name="main warehouse", code="WH2")
    assert response.status_code == 409
    assert field_errors(response) == {"name": "A warehouse with this name already exists"}


@pytest.mark.parametrize("code", ["", "has space", "-LEADING", "x" * 33, "ÄBC"])
def test_invalid_warehouse_code_is_rejected(md, code):
    assert md.post("/warehouses", name="Main", code=code).status_code == 422


def test_warehouse_name_is_required(md):
    assert md.post("/warehouses", code="WH1").status_code == 422
    assert md.post("/warehouses", name=" ", code="WH1").status_code == 422


def test_update_warehouse(client, manager, md):
    warehouse = md.warehouse(name="Main", code="WH1")
    response = client.patch(
        f"/api/warehouses/{warehouse['id']}", headers=manager, json={"name": "Main Store", "address": "Dock 4"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Main Store"
    assert response.json()["address"] == "Dock 4"
    assert response.json()["code"] == "WH1"


def test_update_warehouse_to_duplicate_code_is_rejected(client, manager, md):
    md.warehouse(code="WH1")
    other = md.warehouse(code="WH2")
    assert client.patch(f"/api/warehouses/{other['id']}", headers=manager, json={"code": "WH1"}).status_code == 409


def test_list_warehouses(client, manager, md):
    md.warehouse(name="Main Warehouse", code="MAIN")
    closed = md.warehouse(name="Overflow", code="OVF")
    client.patch(f"/api/warehouses/{closed['id']}", headers=manager, json={"is_active": False})

    assert client.get("/api/warehouses", headers=manager).json()["total"] == 2
    assert [w["code"] for w in client.get("/api/warehouses?q=ovf", headers=manager).json()["items"]] == ["OVF"]
    active = client.get("/api/warehouses?is_active=true", headers=manager).json()["items"]
    assert [w["code"] for w in active] == ["MAIN"]


def test_warehouse_with_locations_cannot_be_deleted(client, manager, md):
    warehouse = md.warehouse()
    md.location(warehouse_id=warehouse["id"])
    assert client.delete(f"/api/warehouses/{warehouse['id']}", headers=manager).status_code == 409

    empty = md.warehouse()
    assert client.delete(f"/api/warehouses/{empty['id']}", headers=manager).status_code == 204
    assert client.get(f"/api/warehouses/{empty['id']}", headers=manager).status_code == 404
