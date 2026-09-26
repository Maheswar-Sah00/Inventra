import pytest

from tests.master_data.conftest import field_errors


@pytest.fixture
def refs(md):
    return {"category": md.category(name="Raw Materials"), "unit": md.unit(name="Kilogram", symbol="kg")}


def create(md, refs, **overrides):
    payload = {
        "name": "Steel Rods",
        "sku": "stl-rod-10",
        "category_id": refs["category"]["id"],
        "unit_of_measure_id": refs["unit"]["id"],
        **overrides,
    }
    return md.post("/products", **payload)


def test_create_product(md, refs):
    response = create(md, refs)
    assert response.status_code == 201
    product = response.json()
    assert product["name"] == "Steel Rods"
    assert product["sku"] == "STL-ROD-10"
    assert product["category"] == {"id": refs["category"]["id"], "name": "Raw Materials"}
    assert product["unit_of_measure"] == {"id": refs["unit"]["id"], "name": "Kilogram", "symbol": "kg"}
    assert product["initial_stock"] == 0
    assert product["initial_location"] is None
    assert product["is_active"] is True


def test_create_product_with_initial_stock(md, refs):
    location = md.location(name="Rack A", code="A")
    response = create(md, refs, initial_stock="12.5", initial_location_id=location["id"])
    assert response.status_code == 201
    product = response.json()
    assert product["initial_stock"] == 12.5
    assert product["initial_location"]["id"] == location["id"]
    assert product["initial_location"]["warehouse"]["id"] == location["warehouse_id"]


def test_initial_stock_requires_a_usable_location(client, manager, md, refs):
    response = create(md, refs, initial_stock=10)
    assert response.status_code == 422
    assert "initial_location_id" in field_errors(response)

    assert field_errors(create(md, refs, initial_stock=10, initial_location_id=9999)) == {
        "initial_location_id": "Location not found"
    }

    location = md.location()
    client.patch(f"/api/warehouses/{location['warehouse_id']}", headers=manager, json={"is_active": False})
    assert field_errors(create(md, refs, initial_stock=10, initial_location_id=location["id"])) == {
        "initial_location_id": "This location's warehouse is inactive"
    }


def test_location_is_ignored_without_initial_stock(md, refs):
    location = md.location()
    product = create(md, refs, initial_location_id=location["id"]).json()
    assert product["initial_location_id"] is None


@pytest.mark.parametrize("quantity", [-1, "-0.001", "1.2345", "abc", 10**12])
def test_invalid_initial_stock_is_rejected(md, refs, quantity):
    assert create(md, refs, initial_stock=quantity, initial_location_id=md.location()["id"]).status_code == 422


def test_duplicate_sku_is_rejected(md, refs):
    assert create(md, refs, sku="STL-ROD-10").status_code == 201
    response = create(md, refs, name="Other", sku=" stl-rod-10 ")
    assert response.status_code == 409
    assert field_errors(response) == {"sku": "A product with this SKU already exists"}


def test_sku_of_inactive_product_cannot_be_reused(client, manager, md, refs):
    product = create(md, refs, sku="OLD-1").json()
    client.patch(f"/api/products/{product['id']}", headers=manager, json={"is_active": False})
    assert create(md, refs, sku="OLD-1").status_code == 409


@pytest.mark.parametrize(
    "field, value",
    [("name", ""), ("name", "   "), ("sku", ""), ("sku", "has space"), ("sku", "x" * 65)],
)
def test_name_and_sku_validation(md, refs, field, value):
    assert create(md, refs, **{field: value}).status_code == 422


@pytest.mark.parametrize("missing", ["name", "sku", "category_id", "unit_of_measure_id"])
def test_required_fields(md, refs, missing):
    payload = {"name": "P", "sku": "P-1", "category_id": refs["category"]["id"], "unit_of_measure_id": refs["unit"]["id"]}
    del payload[missing]
    assert md.post("/products", **payload).status_code == 422


def test_invalid_category_is_rejected(md, refs):
    response = create(md, refs, category_id=9999)
    assert response.status_code == 422
    assert field_errors(response) == {"category_id": "Category not found"}


def test_invalid_unit_is_rejected(md, refs):
    response = create(md, refs, unit_of_measure_id=9999)
    assert response.status_code == 422
    assert field_errors(response) == {"unit_of_measure_id": "Unit of measure not found"}


def test_retrieve_product(client, manager, md, refs):
    product = create(md, refs).json()
    assert client.get(f"/api/products/{product['id']}", headers=manager).json() == product
    assert client.get("/api/products/9999", headers=manager).status_code == 404


def test_update_product(client, manager, md, refs):
    product = create(md, refs).json()
    new_category = md.category(name="Finished Goods")
    new_unit = md.unit(name="Piece", symbol="pc")
    response = client.patch(
        f"/api/products/{product['id']}",
        headers=manager,
        json={"name": "Steel Rods 12mm", "sku": "stl-rod-12", "category_id": new_category["id"], "unit_of_measure_id": new_unit["id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Steel Rods 12mm"
    assert body["sku"] == "STL-ROD-12"
    assert body["category"]["name"] == "Finished Goods"
    assert body["unit_of_measure"]["symbol"] == "pc"


def test_update_validates_references_and_uniqueness(client, manager, md, refs):
    create(md, refs, sku="TAKEN")
    product = create(md, refs, sku="MINE").json()
    url = f"/api/products/{product['id']}"
    assert client.patch(url, headers=manager, json={"sku": "taken"}).status_code == 409
    assert field_errors(client.patch(url, headers=manager, json={"category_id": 9999})) == {"category_id": "Category not found"}
    assert client.patch(url, headers=manager, json={"unit_of_measure_id": 9999}).status_code == 422
    assert client.patch(url, headers=manager, json={"name": None}).status_code == 422
    # Keeping the current SKU is not a conflict.
    assert client.patch(url, headers=manager, json={"sku": "MINE"}).status_code == 200


def test_initial_stock_cannot_be_changed_after_creation(client, manager, md, refs):
    product = create(md, refs).json()
    response = client.patch(f"/api/products/{product['id']}", headers=manager, json={"initial_stock": 100})
    assert response.status_code == 422


def test_product_keeps_archived_category(client, manager, md, refs):
    product = create(md, refs).json()
    client.patch(f"/api/categories/{refs['category']['id']}", headers=manager, json={"is_active": False})
    # Unrelated edits still work even though the category is archived.
    assert client.patch(f"/api/products/{product['id']}", headers=manager, json={"name": "Renamed"}).status_code == 200


@pytest.fixture
def catalogue(client, manager, md):
    raw = md.category(name="Raw Materials")
    finished = md.category(name="Finished Goods")
    kg = md.unit(name="Kilogram", symbol="kg")
    pc = md.unit(name="Piece", symbol="pc")
    md.product(name="Steel Rods", sku="STL-ROD", category_id=raw["id"], unit_of_measure_id=kg["id"])
    md.product(name="Steel Sheet", sku="STL-SHT", category_id=raw["id"], unit_of_measure_id=kg["id"])
    md.product(name="Office Chair", sku="CHR-001", category_id=finished["id"], unit_of_measure_id=pc["id"])
    old = md.product(name="Old Table", sku="TBL-OLD", category_id=finished["id"], unit_of_measure_id=pc["id"])
    client.patch(f"/api/products/{old['id']}", headers=manager, json={"is_active": False})
    return {"raw": raw, "finished": finished, "kg": kg, "pc": pc}


def skus(client, headers, query=""):
    return [p["sku"] for p in client.get(f"/api/products{query}", headers=headers).json()["items"]]


def test_search_products_by_sku(client, manager, catalogue):
    assert skus(client, manager, "?q=chr-0") == ["CHR-001"]
    assert skus(client, manager, "?q=STL") == ["STL-ROD", "STL-SHT"]


def test_search_products_by_name(client, manager, catalogue):
    assert skus(client, manager, "?q=chair") == ["CHR-001"]


def test_filter_products_by_category(client, manager, catalogue):
    assert skus(client, manager, f"?category_id={catalogue['finished']['id']}") == ["CHR-001", "TBL-OLD"]
    assert skus(client, manager, f"?category_id={catalogue['raw']['id']}&q=sheet") == ["STL-SHT"]


def test_filter_products_by_unit_and_status(client, manager, catalogue):
    assert skus(client, manager, f"?unit_of_measure_id={catalogue['pc']['id']}&is_active=true") == ["CHR-001"]
    assert skus(client, manager, "?is_active=false") == ["TBL-OLD"]


def test_product_list_is_paginated_and_sorted(client, manager, catalogue):
    page = client.get("/api/products?limit=2", headers=manager).json()
    assert page["total"] == 4 and page["limit"] == 2 and page["offset"] == 0
    assert [p["name"] for p in page["items"]] == ["Office Chair", "Old Table"]
    assert client.get("/api/products?limit=0", headers=manager).status_code == 422
    assert client.get("/api/products?limit=501", headers=manager).status_code == 422


def test_delete_product(client, manager, md, refs):
    product = create(md, refs).json()
    rule = md.rule(product_id=product["id"])
    assert client.delete(f"/api/products/{product['id']}", headers=manager).status_code == 204
    assert client.get(f"/api/products/{product['id']}", headers=manager).status_code == 404
    # Its reorder rules are configuration of the product and go with it.
    assert client.get(f"/api/reorder-rules/{rule['id']}", headers=manager).status_code == 404
