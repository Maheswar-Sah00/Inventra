import pytest

from tests.master_data.conftest import field_errors


def test_create_category(md):
    response = md.post("/categories", name="  Raw   Materials ", description="  Metals and plastics ")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Raw Materials"
    assert body["description"] == "Metals and plastics"
    assert body["is_active"] is True
    assert body["created_at"].endswith("Z")  # UTC


def test_duplicate_category_name_is_rejected_case_insensitively(md):
    md.category(name="Raw Materials")
    response = md.post("/categories", name="raw materials")
    assert response.status_code == 409
    assert field_errors(response) == {"name": "A category with this name already exists"}


@pytest.mark.parametrize("name", ["", "   "])
def test_category_name_is_required(md, name):
    assert md.post("/categories", name=name).status_code == 422
    assert md.post("/categories", description="no name").status_code == 422


def test_update_category(client, manager, md):
    category = md.category(name="Packaging")
    response = client.patch(
        f"/api/categories/{category['id']}", headers=manager, json={"name": "Packaging Materials", "description": None}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Packaging Materials"
    assert response.json()["description"] is None


def test_update_to_existing_name_is_rejected(client, manager, md):
    md.category(name="Raw Materials")
    other = md.category(name="Finished Goods")
    response = client.patch(f"/api/categories/{other['id']}", headers=manager, json={"name": "RAW MATERIALS"})
    assert response.status_code == 409


def test_renaming_to_own_name_with_different_case_is_allowed(client, manager, md):
    category = md.category(name="Spares")
    response = client.patch(f"/api/categories/{category['id']}", headers=manager, json={"name": "SPARES"})
    assert response.status_code == 200


def test_update_rejects_null_name_and_unknown_fields(client, manager, md):
    category = md.category()
    assert client.patch(f"/api/categories/{category['id']}", headers=manager, json={"name": None}).status_code == 422
    assert client.patch(f"/api/categories/{category['id']}", headers=manager, json={"id": 99}).status_code == 422


def test_list_search_and_filter_categories(client, manager, md):
    md.category(name="Raw Materials")
    md.category(name="Finished Goods")
    archived = md.category(name="Old Stuff")
    client.patch(f"/api/categories/{archived['id']}", headers=manager, json={"is_active": False})

    everything = client.get("/api/categories", headers=manager).json()
    assert everything["total"] == 3
    assert [c["name"] for c in everything["items"]] == ["Finished Goods", "Old Stuff", "Raw Materials"]

    assert [c["name"] for c in client.get("/api/categories?q=raw", headers=manager).json()["items"]] == ["Raw Materials"]
    active = client.get("/api/categories?is_active=true", headers=manager).json()
    assert {c["name"] for c in active["items"]} == {"Raw Materials", "Finished Goods"}

    page = client.get("/api/categories?limit=2&offset=2", headers=manager).json()
    assert page["total"] == 3 and page["limit"] == 2 and page["offset"] == 2
    assert [c["name"] for c in page["items"]] == ["Raw Materials"]


def test_search_treats_wildcards_literally(client, manager, md):
    md.category(name="100% Cotton")
    md.category(name="Cotton")
    assert client.get("/api/categories?q=%25", headers=manager).json()["total"] == 1


def test_get_category_and_404(client, manager, md):
    category = md.category()
    assert client.get(f"/api/categories/{category['id']}", headers=manager).json() == category
    assert client.get("/api/categories/9999", headers=manager).status_code == 404


def test_unused_category_can_be_deleted(client, manager, md):
    category = md.category()
    assert client.delete(f"/api/categories/{category['id']}", headers=manager).status_code == 204
    assert client.get(f"/api/categories/{category['id']}", headers=manager).status_code == 404


def test_category_used_by_products_cannot_be_deleted_but_can_be_deactivated(client, manager, md):
    category = md.category()
    product = md.product(category_id=category["id"])

    response = client.delete(f"/api/categories/{category['id']}", headers=manager)
    assert response.status_code == 409
    assert "Deactivate" in response.json()["detail"]

    assert client.patch(f"/api/categories/{category['id']}", headers=manager, json={"is_active": False}).status_code == 200
    # Existing products keep their (now archived) category...
    assert client.get(f"/api/products/{product['id']}", headers=manager).json()["category"]["id"] == category["id"]
    # ...but new products cannot use it.
    response = md.post(
        "/products", name="New", sku="NEW-1", category_id=category["id"], unit_of_measure_id=md.unit()["id"]
    )
    assert response.status_code == 422
    assert field_errors(response) == {"category_id": "Category is inactive"}
