def transfer(inv, source, destination, lines, **extra):
    return inv.create(
        "/transfers",
        {
            "source_location_id": source["id"],
            "destination_location_id": destination["id"],
            "items": [{"product_id": p, "quantity": q} for p, q in lines],
            **extra,
        },
    )


def total(inv, product_id):
    return inv.get(f"/stock/products/{product_id}").json()["total_quantity"]


def test_transfer_moves_stock_and_keeps_total(inv, world):
    steel = world.steel["id"]
    inv.receive(steel, world.rack_a["id"], 100)
    inv.receive(steel, world.rack_b["id"], 20)
    assert total(inv, steel) == 120

    doc = transfer(inv, world.rack_a, world.rack_b, [(steel, 30)])
    assert doc["reference"] == f"TRF-{doc['id']:06d}"
    assert doc["items"][0]["available_quantity"] == 100
    done = inv.action(f"/transfers/{doc['id']}/validate")
    assert done["status"] == "DONE"

    assert inv.stock(steel, world.rack_a["id"]) == 70
    assert inv.stock(steel, world.rack_b["id"]) == 50
    assert total(inv, steel) == 120

    [movement] = inv.movements(reference_type="TRANSFER", reference_id=doc["id"])
    assert movement["movement_type"] == "TRANSFER"
    assert movement["quantity"] == 30
    assert movement["source_location_id"] == world.rack_a["id"]
    assert movement["destination_location_id"] == world.rack_b["id"]


def test_transfer_between_warehouses(inv, world):
    inv.receive(world.chair["id"], world.rack_a["id"], 10)
    doc = transfer(inv, world.rack_a, world.rack_c, [(world.chair["id"], 10)])
    inv.action(f"/transfers/{doc['id']}/validate")
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 0
    assert inv.stock(world.chair["id"], world.rack_c["id"]) == 10
    by_location = inv.get(f"/stock/products/{world.chair['id']}").json()["locations"]
    assert [(row["location"]["warehouse"]["code"], row["quantity"]) for row in by_location] == [("WH2", 10)]


def test_insufficient_source_stock_rejects_entire_transfer(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    inv.receive(world.chair["id"], world.rack_a["id"], 1)
    doc = transfer(inv, world.rack_a, world.rack_b, [(world.steel["id"], 30), (world.chair["id"], 5)])
    response = inv.post(f"/transfers/{doc['id']}/validate")
    assert response.status_code == 409
    assert "CHR at MAIN / Rack A (available 1, requested 5)" in response.json()["detail"]
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 100
    assert inv.stock(world.steel["id"], world.rack_b["id"]) == 0
    assert inv.get(f"/transfers/{doc['id']}").json()["status"] == "DRAFT"
    assert inv.movements(reference_type="TRANSFER") == []


def test_source_and_destination_must_differ(inv, world):
    payload = {
        "source_location_id": world.rack_a["id"],
        "destination_location_id": world.rack_a["id"],
        "items": [{"product_id": world.steel["id"], "quantity": 1}],
    }
    response = inv.post("/transfers", payload)
    assert response.status_code == 422
    assert "different locations" in response.text

    doc = transfer(inv, world.rack_a, world.rack_b, [(world.steel["id"], 1)])
    response = inv.patch(f"/transfers/{doc['id']}", {"destination_location_id": world.rack_a["id"]})
    assert response.status_code == 422


def test_confirm_reports_waiting_or_ready(inv, world):
    doc = transfer(inv, world.rack_a, world.rack_b, [(world.steel["id"], 5)])
    assert inv.action(f"/transfers/{doc['id']}/confirm")["status"] == "WAITING"
    inv.receive(world.steel["id"], world.rack_a["id"], 5)
    assert inv.action(f"/transfers/{doc['id']}/confirm")["status"] == "READY"


def test_second_validation_does_not_duplicate(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    doc = transfer(inv, world.rack_a, world.rack_b, [(world.steel["id"], 4)])
    inv.action(f"/transfers/{doc['id']}/validate")
    inv.action(f"/transfers/{doc['id']}/validate")
    assert inv.stock(world.steel["id"], world.rack_a["id"]) == 6
    assert inv.stock(world.steel["id"], world.rack_b["id"]) == 4
    assert len(inv.movements(reference_type="TRANSFER")) == 1


def test_list_transfers_matches_either_side(inv, world):
    a = transfer(inv, world.rack_a, world.rack_b, [(world.steel["id"], 1)])
    b = transfer(inv, world.rack_c, world.rack_a, [(world.steel["id"], 1)])
    refs = lambda **p: [t["reference"] for t in inv.get("/transfers", **p).json()["items"]]  # noqa: E731
    assert refs(warehouse_id=world.second["id"]) == [b["reference"]]
    assert refs(location_id=world.rack_a["id"]) == [b["reference"], a["reference"]]
    assert refs(location_id=world.rack_b["id"]) == [a["reference"]]
