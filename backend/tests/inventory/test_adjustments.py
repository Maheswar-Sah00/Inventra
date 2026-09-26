import pytest


def adjustment(inv, location, counts, reason="Cycle count"):
    return inv.create(
        "/adjustments",
        {
            "location_id": location["id"],
            "reason": reason,
            "items": [{"product_id": p, "counted_quantity": q} for p, q in counts],
        },
    )


def test_counted_quantity_updates_stock(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 97)], reason="3 kg steel damaged")
    assert doc["reference"] == f"ADJ-{doc['id']:06d}"
    assert doc["items"][0]["current_quantity"] == 100
    assert doc["items"][0]["recorded_quantity"] is None

    done = inv.action(f"/adjustments/{doc['id']}/validate")
    assert done["status"] == "DONE"
    line = done["items"][0]
    assert (line["recorded_quantity"], line["counted_quantity"], line["difference"]) == (100, 97, -3)
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 97

    [movement] = inv.movements(reference_type="ADJUSTMENT", reference_id=doc["id"])
    assert movement["movement_type"] == "ADJUSTMENT"
    assert movement["quantity"] == -3
    assert movement["source_location_id"] == world.rack_a["id"]
    assert movement["destination_location_id"] is None


def test_positive_adjustment_and_new_position(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 12), (world.chair["id"], 5)])
    lines = inv.action(f"/adjustments/{doc['id']}/validate")["items"]
    assert [(l["recorded_quantity"], l["difference"]) for l in lines] == [(10, 2), (0, 5)]
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 5
    movements = inv.movements(reference_type="ADJUSTMENT")
    assert sorted(m["quantity"] for m in movements) == [2, 5]
    assert all(m["destination_location_id"] == world.rack_a["id"] for m in movements)


def test_no_difference_records_no_movement(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 10)])
    line = inv.action(f"/adjustments/{doc['id']}/validate")["items"][0]
    assert line["difference"] == 0
    assert inv.movements(reference_type="ADJUSTMENT") == []


def test_recorded_quantity_is_taken_at_validation(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 97)])
    inv.receive(world.steel["id"], world.rack_a["id"], 10)  # stock changes after the count was entered
    line = inv.action(f"/adjustments/{doc['id']}/validate")["items"][0]
    assert (line["recorded_quantity"], line["difference"]) == (110, -13)
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 97


@pytest.mark.parametrize("counted", [-1, "-0.001", "1.2345", None])
def test_invalid_counted_quantity_rejected(inv, world, counted):
    payload = {"location_id": world.rack_a["id"], "reason": "Count", "items": [{"product_id": world.steel["id"], "counted_quantity": counted}]}
    assert inv.post("/adjustments", payload).status_code == 422


def test_counted_zero_is_allowed(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 4)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 0)])
    inv.action(f"/adjustments/{doc['id']}/validate")
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 0


def test_reason_and_location_required(inv, world):
    items = [{"product_id": world.steel["id"], "counted_quantity": 1}]
    assert inv.post("/adjustments", {"location_id": world.rack_a["id"], "items": items}).status_code == 422
    assert inv.post("/adjustments", {"location_id": world.rack_a["id"], "reason": " ", "items": items}).status_code == 422
    assert inv.post("/adjustments", {"reason": "Count", "items": items}).status_code == 422
    assert inv.post("/adjustments", {"location_id": 9999, "reason": "Count", "items": items}).status_code == 422


def test_duplicate_validation_prevented(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    doc = adjustment(inv, world.rack_a, [(world.steel["id"], 97)])
    inv.action(f"/adjustments/{doc['id']}/validate")
    inv.receive(world.steel["id"], world.rack_a["id"], 3)  # 100
    again = inv.action(f"/adjustments/{doc['id']}/validate")
    assert again["items"][0]["difference"] == -3
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 100  # not reset to 97 again
    assert len(inv.movements(reference_type="ADJUSTMENT")) == 1
