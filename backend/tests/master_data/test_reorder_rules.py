import pytest

from tests.master_data.conftest import field_errors


def test_create_reorder_rule(md):
    product = md.product(name="Steel Rods", sku="STL")
    location = md.location(name="Rack A", code="A")
    response = md.post(
        "/reorder-rules", product_id=product["id"], location_id=location["id"], minimum_quantity="10.5", target_quantity=50
    )
    assert response.status_code == 201
    rule = response.json()
    assert rule["minimum_quantity"] == 10.5
    assert rule["target_quantity"] == 50
    assert rule["is_active"] is True
    assert rule["product"] == {"id": product["id"], "name": "Steel Rods", "sku": "STL", "is_active": True}
    assert rule["location"]["name"] == "Rack A"
    assert rule["location"]["warehouse"]["id"] == location["warehouse_id"]


def test_invalid_product_is_rejected(md):
    response = md.post("/reorder-rules", product_id=9999, location_id=md.location()["id"], minimum_quantity=1, target_quantity=2)
    assert response.status_code == 422
    assert field_errors(response) == {"product_id": "Product not found"}


def test_inactive_product_is_rejected(client, manager, md):
    product = md.product()
    client.patch(f"/api/products/{product['id']}", headers=manager, json={"is_active": False})
    response = md.post("/reorder-rules", product_id=product["id"], location_id=md.location()["id"], minimum_quantity=1, target_quantity=2)
    assert field_errors(response) == {"product_id": "Product is inactive"}


def test_invalid_location_is_rejected(md):
    response = md.post("/reorder-rules", product_id=md.product()["id"], location_id=9999, minimum_quantity=1, target_quantity=2)
    assert response.status_code == 422
    assert field_errors(response) == {"location_id": "Location not found"}


def test_inactive_location_or_warehouse_is_rejected(client, manager, md):
    product = md.product()
    location = md.location()
    client.patch(f"/api/locations/{location['id']}", headers=manager, json={"is_active": False})
    response = md.post("/reorder-rules", product_id=product["id"], location_id=location["id"], minimum_quantity=1, target_quantity=2)
    assert field_errors(response) == {"location_id": "Location is inactive"}

    other = md.location()
    client.patch(f"/api/warehouses/{other['warehouse_id']}", headers=manager, json={"is_active": False})
    response = md.post("/reorder-rules", product_id=product["id"], location_id=other["id"], minimum_quantity=1, target_quantity=2)
    assert field_errors(response) == {"location_id": "This location's warehouse is inactive"}


@pytest.mark.parametrize("minimum", [-1, "-0.5", "abc", None])
def test_minimum_quantity_validation(md, minimum):
    response = md.post(
        "/reorder-rules",
        product_id=md.product()["id"],
        location_id=md.location()["id"],
        minimum_quantity=minimum,
        target_quantity=10,
    )
    assert response.status_code == 422


def test_target_below_minimum_is_rejected(md):
    response = md.post(
        "/reorder-rules", product_id=md.product()["id"], location_id=md.location()["id"], minimum_quantity=10, target_quantity=5
    )
    assert response.status_code == 422
    assert field_errors(response)["target_quantity"].endswith(
        "Target quantity must be greater than or equal to the minimum quantity"
    )


def test_target_equal_to_minimum_is_allowed(md):
    assert md.rule(minimum_quantity=0, target_quantity=0)["target_quantity"] == 0


def test_one_rule_per_product_and_location(md):
    rule = md.rule()
    response = md.post(
        "/reorder-rules", product_id=rule["product_id"], location_id=rule["location_id"], minimum_quantity=1, target_quantity=2
    )
    assert response.status_code == 409
    assert field_errors(response) == {"location_id": "This product already has a reorder rule for this location"}
    # The same product can have a rule at another location.
    assert md.rule(product_id=rule["product_id"])["id"] != rule["id"]


def test_update_reorder_rule(client, manager, md):
    rule = md.rule(minimum_quantity=5, target_quantity=20)
    url = f"/api/reorder-rules/{rule['id']}"
    response = client.patch(url, headers=manager, json={"minimum_quantity": 8, "is_active": False})
    assert response.status_code == 200
    assert response.json()["minimum_quantity"] == 8 and response.json()["is_active"] is False

    # Checked against the stored target when only the minimum changes.
    response = client.patch(url, headers=manager, json={"minimum_quantity": 25})
    assert response.status_code == 422
    assert field_errors(response) == {"target_quantity": "Target quantity must be greater than or equal to the minimum quantity"}
    assert client.patch(url, headers=manager, json={"target_quantity": 7}).status_code == 422
    assert client.patch(url, headers=manager, json={"minimum_quantity": 25, "target_quantity": 30}).status_code == 200


def test_product_and_location_of_a_rule_cannot_change(client, manager, md):
    rule = md.rule()
    response = client.patch(f"/api/reorder-rules/{rule['id']}", headers=manager, json={"product_id": md.product()["id"]})
    assert response.status_code == 422


def test_list_reorder_rules_with_filters(client, manager, md):
    main, other = md.warehouse(), md.warehouse()
    rack_a = md.location(warehouse_id=main["id"])
    rack_b = md.location(warehouse_id=other["id"])
    steel = md.product()
    wood = md.product()
    r1 = md.rule(product_id=steel["id"], location_id=rack_a["id"])
    r2 = md.rule(product_id=steel["id"], location_id=rack_b["id"])
    r3 = md.rule(product_id=wood["id"], location_id=rack_a["id"])
    client.patch(f"/api/reorder-rules/{r3['id']}", headers=manager, json={"is_active": False})

    def ids(query):
        return [r["id"] for r in client.get(f"/api/reorder-rules{query}", headers=manager).json()["items"]]

    assert ids("") == [r1["id"], r2["id"], r3["id"]]
    assert ids(f"?product_id={steel['id']}") == [r1["id"], r2["id"]]
    assert ids(f"?location_id={rack_a['id']}") == [r1["id"], r3["id"]]
    assert ids(f"?warehouse_id={main['id']}") == [r1["id"], r3["id"]]
    assert ids(f"?warehouse_id={main['id']}&is_active=true") == [r1["id"]]
    assert client.get(f"/api/reorder-rules?warehouse_id={main['id']}", headers=manager).json()["total"] == 2


def test_retrieve_and_delete_reorder_rule(client, manager, md):
    rule = md.rule()
    assert client.get(f"/api/reorder-rules/{rule['id']}", headers=manager).json() == rule
    assert client.delete(f"/api/reorder-rules/{rule['id']}", headers=manager).status_code == 204
    assert client.get(f"/api/reorder-rules/{rule['id']}", headers=manager).status_code == 404
