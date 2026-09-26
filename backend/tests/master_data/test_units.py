from tests.master_data.conftest import field_errors


def test_create_and_retrieve_unit(client, manager, md):
    response = md.post("/units", name="Kilogram", symbol="kg")
    assert response.status_code == 201
    unit = response.json()
    assert unit["name"] == "Kilogram" and unit["symbol"] == "kg" and unit["is_active"] is True
    assert client.get(f"/api/units/{unit['id']}", headers=manager).json() == unit


def test_unit_requires_name_and_symbol(md):
    assert md.post("/units", name="Kilogram").status_code == 422
    assert md.post("/units", symbol="kg").status_code == 422
    assert md.post("/units", name="Kilogram", symbol=" ").status_code == 422
    assert md.post("/units", name="Kilogram", symbol="x" * 17).status_code == 422


def test_duplicate_unit_name_or_symbol_is_rejected(md):
    md.unit(name="Kilogram", symbol="kg")
    response = md.post("/units", name="kilogram", symbol="kilo")
    assert response.status_code == 409
    assert field_errors(response) == {"name": "A unit with this name already exists"}
    response = md.post("/units", name="Kilo", symbol="KG")
    assert response.status_code == 409
    assert field_errors(response) == {"symbol": "A unit with this symbol already exists"}


def test_update_unit(client, manager, md):
    unit = md.unit(name="Meter", symbol="mtr")
    response = client.patch(f"/api/units/{unit['id']}", headers=manager, json={"symbol": "m", "is_active": False})
    assert response.status_code == 200
    assert response.json()["symbol"] == "m"
    assert response.json()["is_active"] is False


def test_list_units_search_by_symbol(client, manager, md):
    md.unit(name="Kilogram", symbol="kg")
    md.unit(name="Piece", symbol="pc")
    names = [u["name"] for u in client.get("/api/units?q=pc", headers=manager).json()["items"]]
    assert names == ["Piece"]


def test_unit_used_by_product_cannot_be_deleted(client, manager, md):
    unit = md.unit()
    md.product(unit_of_measure_id=unit["id"])
    assert client.delete(f"/api/units/{unit['id']}", headers=manager).status_code == 409
    unused = md.unit()
    assert client.delete(f"/api/units/{unused['id']}", headers=manager).status_code == 204


def test_inactive_unit_cannot_be_used_for_new_products(client, manager, md):
    unit = md.unit()
    client.patch(f"/api/units/{unit['id']}", headers=manager, json={"is_active": False})
    response = md.post("/products", name="P", sku="P-1", category_id=md.category()["id"], unit_of_measure_id=unit["id"])
    assert response.status_code == 422
    assert field_errors(response) == {"unit_of_measure_id": "Unit of measure is inactive"}
