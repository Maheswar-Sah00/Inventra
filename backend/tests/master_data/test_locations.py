from tests.master_data.conftest import field_errors


def test_create_and_retrieve_location(client, manager, md):
    warehouse = md.warehouse(name="Main Warehouse", code="MAIN")
    response = md.post("/locations", warehouse_id=warehouse["id"], name="Rack A", code="rack-a")
    assert response.status_code == 201
    location = response.json()
    assert location["code"] == "RACK-A"
    assert location["warehouse_id"] == warehouse["id"]
    assert location["warehouse"] == {"id": warehouse["id"], "name": "Main Warehouse", "code": "MAIN", "is_active": True}

    assert client.get(f"/api/locations/{location['id']}", headers=manager).json() == location
    assert client.get("/api/locations/9999", headers=manager).status_code == 404


def test_nonexistent_warehouse_is_rejected(md):
    response = md.post("/locations", warehouse_id=9999, name="Rack A", code="A")
    assert response.status_code == 422
    assert field_errors(response) == {"warehouse_id": "Warehouse not found"}


def test_inactive_warehouse_is_rejected(client, manager, md):
    warehouse = md.warehouse()
    client.patch(f"/api/warehouses/{warehouse['id']}", headers=manager, json={"is_active": False})
    response = md.post("/locations", warehouse_id=warehouse["id"], name="Rack A", code="A")
    assert response.status_code == 422
    assert field_errors(response) == {"warehouse_id": "Warehouse is inactive"}


def test_location_requires_warehouse_name_and_code(md):
    warehouse = md.warehouse()
    assert md.post("/locations", name="Rack A", code="A").status_code == 422
    assert md.post("/locations", warehouse_id=warehouse["id"], code="A").status_code == 422
    assert md.post("/locations", warehouse_id=warehouse["id"], name="Rack A").status_code == 422


def test_duplicate_code_in_same_warehouse_is_rejected(md):
    warehouse = md.warehouse()
    md.location(warehouse_id=warehouse["id"], name="Rack A", code="A")
    response = md.post("/locations", warehouse_id=warehouse["id"], name="Rack A2", code="a")
    assert response.status_code == 409
    assert field_errors(response) == {"code": "This warehouse already has a location with this code"}


def test_duplicate_name_in_same_warehouse_is_rejected(md):
    warehouse = md.warehouse()
    md.location(warehouse_id=warehouse["id"], name="Rack A", code="A")
    response = md.post("/locations", warehouse_id=warehouse["id"], name="rack a", code="B")
    assert response.status_code == 409
    assert field_errors(response) == {"name": "This warehouse already has a location with this name"}


def test_same_code_in_different_warehouses_is_allowed(md):
    first, second = md.warehouse(), md.warehouse()
    md.location(warehouse_id=first["id"], name="Rack A", code="A")
    assert md.post("/locations", warehouse_id=second["id"], name="Rack A", code="A").status_code == 201


def test_update_location(client, manager, md):
    location = md.location(name="Rack A", code="A")
    response = client.patch(f"/api/locations/{location['id']}", headers=manager, json={"name": "Production Floor"})
    assert response.status_code == 200
    assert response.json()["name"] == "Production Floor"


def test_update_location_to_duplicate_code_is_rejected(client, manager, md):
    warehouse = md.warehouse()
    md.location(warehouse_id=warehouse["id"], code="A")
    other = md.location(warehouse_id=warehouse["id"], code="B")
    assert client.patch(f"/api/locations/{other['id']}", headers=manager, json={"code": "A"}).status_code == 409


def test_location_cannot_move_to_another_warehouse(client, manager, md):
    location = md.location()
    other = md.warehouse()
    response = client.patch(f"/api/locations/{location['id']}", headers=manager, json={"warehouse_id": other["id"]})
    assert response.status_code == 422


def test_list_locations_filters(client, manager, md):
    main, overflow = md.warehouse(), md.warehouse()
    md.location(warehouse_id=main["id"], name="Rack A", code="A")
    md.location(warehouse_id=main["id"], name="Rack B", code="B")
    closed = md.location(warehouse_id=overflow["id"], name="Bay 1", code="BAY1")
    client.patch(f"/api/locations/{closed['id']}", headers=manager, json={"is_active": False})

    in_main = client.get(f"/api/locations?warehouse_id={main['id']}", headers=manager).json()
    assert [loc["name"] for loc in in_main["items"]] == ["Rack A", "Rack B"]
    assert client.get("/api/locations?q=bay", headers=manager).json()["total"] == 1
    assert client.get("/api/locations?is_active=false", headers=manager).json()["items"][0]["code"] == "BAY1"


def test_location_delete_rules(client, manager, md):
    unused = md.location()
    assert client.delete(f"/api/locations/{unused['id']}", headers=manager).status_code == 204

    # A location that holds a product's initial stock is part of its history and cannot be deleted.
    used = md.location()
    md.product(initial_stock=5, initial_location_id=used["id"])
    assert client.delete(f"/api/locations/{used['id']}", headers=manager).status_code == 409
