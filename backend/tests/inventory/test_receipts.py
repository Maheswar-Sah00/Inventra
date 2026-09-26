import pytest


def receipt_payload(world, **overrides):
    return {
        "supplier_name": "Acme Metals",
        "supplier_reference": "INV-778",
        "destination_location_id": world.rack_a["id"],
        "scheduled_date": "2026-10-01",
        "items": [{"product_id": world.steel["id"], "quantity": 50}],
        **overrides,
    }


def test_create_receipt(inv, world):
    receipt = inv.create("/receipts", receipt_payload(world))
    assert receipt["reference"] == f"REC-{receipt['id']:06d}"
    assert receipt["status"] == "DRAFT"
    assert receipt["supplier_name"] == "Acme Metals"
    assert receipt["destination_location"]["code"] == "RACK-A"
    assert receipt["created_by"]["name"] == "Asha Rao"
    assert receipt["validated_by"] is None
    assert receipt["items"][0]["product"]["sku"] == "STL"
    assert receipt["items"][0]["product"]["unit_of_measure"]["symbol"] == "pc"
    assert receipt["items"][0]["quantity"] == 50
    # A draft does not touch stock.
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 0
    assert inv.movements() == []


def test_validate_receipt_increases_stock_and_records_movement(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    receipt = inv.create("/receipts", receipt_payload(world))

    done = inv.action(f"/receipts/{receipt['id']}/validate")
    assert done["status"] == "DONE"
    assert done["validated_by"]["name"] == "Asha Rao"
    assert done["validated_at"] is not None
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 150

    [movement] = inv.movements(reference_type="RECEIPT", reference_id=receipt["id"])
    assert movement["movement_type"] == "RECEIPT"
    assert movement["quantity"] == 50
    assert movement["source_location_id"] is None
    assert movement["destination_location_id"] == world.rack_a["id"]
    assert movement["reference_number"] == receipt["reference"]
    assert movement["performed_by"]["name"] == "Asha Rao"


def test_second_validation_does_not_duplicate_stock(inv, world):
    receipt = inv.create("/receipts", receipt_payload(world))
    first = inv.action(f"/receipts/{receipt['id']}/validate")
    second = inv.action(f"/receipts/{receipt['id']}/validate")
    assert second["status"] == "DONE"
    assert second["validated_at"] == first["validated_at"]
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 50
    assert len(inv.movements(reference_type="RECEIPT", reference_id=receipt["id"])) == 1


def test_multi_line_receipt(inv, world):
    receipt = inv.create(
        "/receipts",
        receipt_payload(world, items=[{"product_id": world.steel["id"], "quantity": "12.5"}, {"product_id": world.chair["id"], "quantity": 4}]),
    )
    inv.action(f"/receipts/{receipt['id']}/validate")
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 12.5
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 4
    assert len(inv.movements(reference_id=receipt["id"], reference_type="RECEIPT")) == 2


@pytest.mark.parametrize("quantity", [0, -5, "1.2345", "abc", None])
def test_invalid_quantity_is_rejected(inv, world, quantity):
    payload = receipt_payload(world, items=[{"product_id": world.steel["id"], "quantity": quantity}])
    assert inv.post("/receipts", payload).status_code == 422


def test_receipt_line_and_header_validation(inv, world, client, manager):
    assert inv.post("/receipts", receipt_payload(world, items=[])).status_code == 422
    assert inv.post("/receipts", receipt_payload(world, supplier_name=" ")).status_code == 422
    duplicate = [{"product_id": world.steel["id"], "quantity": 1}, {"product_id": world.steel["id"], "quantity": 2}]
    assert "only once" in inv.post("/receipts", receipt_payload(world, items=duplicate)).text

    response = inv.post("/receipts", receipt_payload(world, items=[{"product_id": 9999, "quantity": 1}]))
    assert response.status_code == 422 and "not found" in response.json()["detail"]
    response = inv.post("/receipts", receipt_payload(world, destination_location_id=9999))
    assert response.status_code == 422

    client.patch(f"/api/locations/{world.rack_b['id']}", headers=manager, json={"is_active": False})
    assert inv.post("/receipts", receipt_payload(world, destination_location_id=world.rack_b["id"])).status_code == 422
    client.patch(f"/api/products/{world.chair['id']}", headers=manager, json={"is_active": False})
    response = inv.post("/receipts", receipt_payload(world, items=[{"product_id": world.chair["id"], "quantity": 1}]))
    assert "inactive" in response.json()["detail"]


def test_status_lifecycle(inv, world):
    receipt = inv.create("/receipts", receipt_payload(world))
    assert inv.action(f"/receipts/{receipt['id']}/confirm")["status"] == "READY"
    assert inv.action(f"/receipts/{receipt['id']}/confirm")["status"] == "READY"  # idempotent

    # Editing a confirmed receipt returns it to DRAFT.
    edited = inv.patch(f"/receipts/{receipt['id']}", {"items": [{"product_id": world.steel["id"], "quantity": 60}]}).json()
    assert edited["status"] == "DRAFT"
    assert edited["items"][0]["quantity"] == 60

    inv.action(f"/receipts/{receipt['id']}/validate")
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 60
    # DONE is final.
    assert inv.patch(f"/receipts/{receipt['id']}", {"notes": "late"}).status_code == 409
    response = inv.post(f"/receipts/{receipt['id']}/cancel")
    assert response.status_code == 409 and "DONE" in response.json()["detail"]


def test_cancel_receipt(inv, world):
    receipt = inv.create("/receipts", receipt_payload(world))
    canceled = inv.action(f"/receipts/{receipt['id']}/cancel")
    assert canceled["status"] == "CANCELED" and canceled["canceled_at"] is not None
    assert inv.action(f"/receipts/{receipt['id']}/cancel")["status"] == "CANCELED"  # idempotent
    assert inv.post(f"/receipts/{receipt['id']}/validate").status_code == 409
    assert inv.post(f"/receipts/{receipt['id']}/confirm").status_code == 409
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 0


def test_edit_replaces_lines_including_same_product(inv, world):
    receipt = inv.create("/receipts", receipt_payload(world))
    response = inv.patch(
        f"/receipts/{receipt['id']}",
        {
            "supplier_name": "Beta Supplies",
            "destination_location_id": world.rack_b["id"],
            "items": [{"product_id": world.steel["id"], "quantity": 5}, {"product_id": world.chair["id"], "quantity": 2}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["supplier_name"] == "Beta Supplies"
    assert body["destination_location_id"] == world.rack_b["id"]
    assert [(i["product"]["sku"], i["quantity"]) for i in body["items"]] == [("STL", 5), ("CHR", 2)]
    assert inv.patch(f"/receipts/{receipt['id']}", {"status": "DONE"}).status_code == 422


def test_list_receipts_filters(inv, world):
    a = inv.create("/receipts", receipt_payload(world))
    b = inv.create("/receipts", receipt_payload(world, supplier_name="Beta Supplies", destination_location_id=world.rack_c["id"],
                                                items=[{"product_id": world.chair["id"], "quantity": 3}]))
    inv.action(f"/receipts/{b['id']}/validate")

    def refs(**params):
        return [r["reference"] for r in inv.get("/receipts", **params).json()["items"]]

    assert refs() == [b["reference"], a["reference"]]
    assert refs(status="DONE") == [b["reference"]]
    assert inv.get("/receipts", status=["DRAFT", "WAITING", "READY"]).json()["total"] == 1
    assert refs(q="beta") == [b["reference"]]
    assert refs(q=a["reference"]) == [a["reference"]]
    assert refs(warehouse_id=world.second["id"]) == [b["reference"]]
    assert refs(location_id=world.rack_a["id"]) == [a["reference"]]
    assert refs(product_id=world.chair["id"]) == [b["reference"]]
    assert refs(category_id=world.category["id"]) == [a["reference"]]
    assert inv.get("/receipts/9999").status_code == 404


def test_receipts_require_authentication(client):
    assert client.get("/api/receipts").status_code == 401
    assert client.post("/api/receipts/1/validate").status_code == 401
