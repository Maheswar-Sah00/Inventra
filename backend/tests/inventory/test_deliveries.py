def test_create_delivery(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)], customer_name="Globex", scheduled_date="2026-10-02")
    assert delivery["reference"] == f"DEL-{delivery['id']:06d}"
    assert delivery["status"] == "DRAFT"
    assert delivery["customer_name"] == "Globex"
    assert delivery["items"][0]["available_quantity"] == 100
    assert delivery["picked_at"] is None and delivery["packed_at"] is None


def test_full_delivery_flow_decreases_stock(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])

    ready = inv.action(f"/deliveries/{delivery['id']}/confirm")
    assert ready["status"] == "READY"
    picked = inv.action(f"/deliveries/{delivery['id']}/pick")
    assert picked["picked_at"] is not None and picked["picked_by"]["name"] == "Asha Rao"
    # Picking and packing prepare the order but do not move stock.
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 100
    packed = inv.action(f"/deliveries/{delivery['id']}/pack")
    assert packed["packed_at"] is not None and packed["status"] == "READY"
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 100

    done = inv.action(f"/deliveries/{delivery['id']}/validate")
    assert done["status"] == "DONE"
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 90

    [movement] = inv.movements(reference_type="DELIVERY", reference_id=delivery["id"])
    assert movement["movement_type"] == "DELIVERY"
    assert movement["quantity"] == -10
    assert movement["source_location_id"] == world.rack_a["id"]
    assert movement["destination_location_id"] is None


def test_second_validation_does_not_duplicate_stock(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    inv.prepare_delivery(delivery["id"])
    inv.action(f"/deliveries/{delivery['id']}/validate")
    assert inv.action(f"/deliveries/{delivery['id']}/validate")["status"] == "DONE"
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 90
    assert len(inv.movements(reference_type="DELIVERY")) == 1


def test_confirm_without_stock_waits_until_stock_arrives(inv, world):
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    waiting = inv.action(f"/deliveries/{delivery['id']}/confirm")
    assert waiting["status"] == "WAITING"
    assert waiting["items"][0]["available_quantity"] == 0
    assert inv.post(f"/deliveries/{delivery['id']}/pick").status_code == 409

    inv.receive(world.chair["id"], world.rack_a["id"], 10)
    assert inv.action(f"/deliveries/{delivery['id']}/confirm")["status"] == "READY"


def test_steps_must_happen_in_order(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    url = f"/deliveries/{delivery['id']}"
    assert inv.post(f"{url}/pick").status_code == 409  # still DRAFT
    assert inv.post(f"{url}/validate").status_code == 409
    inv.action(f"{url}/confirm")
    assert inv.post(f"{url}/pack").status_code == 409  # not picked
    assert inv.post(f"{url}/validate").status_code == 409  # not packed
    inv.action(f"{url}/pick")
    assert inv.action(f"{url}/pick")["picked_at"] is not None  # idempotent
    assert inv.post(f"{url}/validate").status_code == 409  # still not packed
    inv.action(f"{url}/pack")
    assert inv.action(f"{url}/validate")["status"] == "DONE"


def test_insufficient_stock_rejected_and_stock_unchanged(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 10)
    first = inv.delivery(world.rack_a["id"], [(world.chair["id"], 7)])
    second = inv.delivery(world.rack_a["id"], [(world.chair["id"], 6)])
    inv.prepare_delivery(first["id"])
    inv.prepare_delivery(second["id"])  # both looked fine when picked: stock is not reserved

    inv.action(f"/deliveries/{first['id']}/validate")
    response = inv.post(f"/deliveries/{second['id']}/validate")
    assert response.status_code == 409
    assert "Not enough stock: CHR at MAIN / Rack A (available 3, requested 6)" in response.json()["detail"]

    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 3
    assert inv.get(f"/deliveries/{second['id']}").json()["status"] == "READY"
    assert len(inv.movements(reference_type="DELIVERY")) == 1


def test_multi_line_delivery_is_all_or_nothing(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 50)
    inv.receive(world.steel["id"], world.rack_a["id"], 5)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10), (world.steel["id"], 5)])
    inv.prepare_delivery(delivery["id"])
    # Stock disappears between packing and validation.
    adjustment = inv.create(
        "/adjustments",
        {"location_id": world.rack_a["id"], "reason": "Damaged", "items": [{"product_id": world.steel["id"], "counted_quantity": 2}]},
    )
    inv.action(f"/adjustments/{adjustment['id']}/validate")

    response = inv.post(f"/deliveries/{delivery['id']}/validate")
    assert response.status_code == 409 and "STL" in response.json()["detail"]
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 50  # the line with enough stock was not applied either
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 2


def test_pick_rechecks_availability(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 10)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    inv.action(f"/deliveries/{delivery['id']}/confirm")
    other = inv.delivery(world.rack_a["id"], [(world.chair["id"], 5)])
    inv.prepare_delivery(other["id"])
    inv.action(f"/deliveries/{other['id']}/validate")
    response = inv.post(f"/deliveries/{delivery['id']}/pick")
    assert response.status_code == 409 and "available 5" in response.json()["detail"]


def test_editing_resets_pick_and_pack(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    inv.prepare_delivery(delivery["id"])
    edited = inv.patch(f"/deliveries/{delivery['id']}", {"items": [{"product_id": world.chair["id"], "quantity": 20}]}).json()
    assert edited["status"] == "DRAFT"
    assert edited["picked_at"] is None and edited["packed_at"] is None
    inv.prepare_delivery(delivery["id"])
    inv.action(f"/deliveries/{delivery['id']}/validate")
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 80


def test_delivery_validation_rules(inv, world):
    assert inv.post("/deliveries", {"source_location_id": world.rack_a["id"], "items": [{"product_id": world.chair["id"], "quantity": 0}]}).status_code == 422
    assert inv.post("/deliveries", {"source_location_id": 9999, "items": [{"product_id": world.chair["id"], "quantity": 1}]}).status_code == 422
    assert inv.post("/deliveries", {"source_location_id": world.rack_a["id"], "items": [{"product_id": 9999, "quantity": 1}]}).status_code == 422
    assert inv.post("/deliveries", {"items": [{"product_id": world.chair["id"], "quantity": 1}]}).status_code == 422


def test_cancel_delivery_keeps_stock(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 10)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 4)])
    inv.prepare_delivery(delivery["id"])
    assert inv.action(f"/deliveries/{delivery['id']}/cancel")["status"] == "CANCELED"
    assert inv.post(f"/deliveries/{delivery['id']}/validate").status_code == 409
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 10


def test_list_deliveries(inv, world):
    a = inv.delivery(world.rack_a["id"], [(world.chair["id"], 1)], customer_name="Globex")
    b = inv.delivery(world.rack_c["id"], [(world.steel["id"], 1)], customer_name="Initech")
    inv.action(f"/deliveries/{b['id']}/cancel")
    refs = lambda **p: [d["reference"] for d in inv.get("/deliveries", **p).json()["items"]]  # noqa: E731
    assert refs() == [b["reference"], a["reference"]]
    assert refs(q="glob") == [a["reference"]]
    assert refs(status="CANCELED") == [b["reference"]]
    assert refs(warehouse_id=world.second["id"]) == [b["reference"]]
    assert refs(category_id=world.other_category["id"]) == [a["reference"]]
