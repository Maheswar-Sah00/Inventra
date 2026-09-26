from datetime import date, timedelta

import pytest

from app.inventory import services as stock_services


def test_initial_stock_from_product_creation(inv, md, world):
    product = md.product(name="Copper Wire", sku="CU-1", initial_stock="40.5", initial_location_id=world.rack_b["id"])
    assert inv.stock(product["id"], world.rack_b["id"]) == 40.5
    [movement] = inv.movements(product_id=product["id"])
    assert movement["movement_type"] == "INITIAL_STOCK"
    assert movement["quantity"] == 40.5
    assert movement["destination_location_id"] == world.rack_b["id"]
    assert (movement["reference_type"], movement["reference_id"], movement["reference_number"]) == ("PRODUCT", product["id"], "CU-1")
    assert movement["performed_by"]["name"] == "Asha Rao"


def test_stock_list_shape_and_filters(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    inv.receive(world.steel["id"], world.rack_c["id"], 4)
    inv.receive(world.chair["id"], world.rack_b["id"], 2)

    page = inv.get("/stock").json()
    assert page["total"] == 3
    first = page["items"][0]  # sorted by product name, then warehouse, then location
    assert first["product"]["sku"] == "CHR"
    assert first["product"]["category"]["name"] == "Furniture"
    assert first["product"]["unit_of_measure"]["symbol"] == "pc"
    assert first["location"]["warehouse"]["code"] == "MAIN"
    assert first["quantity"] == 2

    def rows(**params):
        return [(r["product"]["sku"], r["location"]["code"], r["quantity"]) for r in inv.get("/stock", **params).json()["items"]]

    assert rows(warehouse_id=world.second["id"]) == [("STL", "RACK-C", 4)]
    assert rows(location_id=world.rack_a["id"]) == [("STL", "RACK-A", 10)]
    assert rows(category_id=world.category["id"]) == [("STL", "RACK-A", 10), ("STL", "RACK-C", 4)]
    assert rows(q="chr") == [("CHR", "RACK-B", 2)]


def test_empty_positions_hidden_by_default(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 5)
    doc = inv.create(
        "/adjustments",
        {"location_id": world.rack_a["id"], "reason": "Lost", "items": [{"product_id": world.steel["id"], "counted_quantity": 0}]},
    )
    inv.action(f"/adjustments/{doc['id']}/validate")
    assert inv.get("/stock").json()["total"] == 0
    assert inv.get("/stock", include_empty=True).json()["items"][0]["quantity"] == 0


def test_product_stock_breakdown(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    inv.receive(world.steel["id"], world.rack_c["id"], "4.25")
    body = inv.get(f"/stock/products/{world.steel['id']}").json()
    assert body["product"]["sku"] == "STL"
    assert body["total_quantity"] == 14.25
    assert [(r["location"]["code"], r["quantity"]) for r in body["locations"]] == [("RACK-A", 10), ("RACK-C", 4.25)]
    assert inv.get(f"/stock/products/{world.steel['id']}", warehouse_id=world.second["id"]).json()["total_quantity"] == 4.25
    assert inv.get("/stock/products/9999").status_code == 404


def test_movement_ledger_filters(inv, world):
    receipt = inv.receive(world.steel["id"], world.rack_a["id"], 10)
    transfer = inv.create(
        "/transfers",
        {"source_location_id": world.rack_a["id"], "destination_location_id": world.rack_c["id"],
         "items": [{"product_id": world.steel["id"], "quantity": 4}]},
    )
    inv.action(f"/transfers/{transfer['id']}/validate")
    inv.receive(world.chair["id"], world.rack_b["id"], 2)

    def types(**params):
        return [m["movement_type"] for m in inv.get("/stock-movements", **params).json()["items"]]

    assert types() == ["RECEIPT", "TRANSFER", "RECEIPT"]  # newest first
    assert types(movement_type=["TRANSFER"]) == ["TRANSFER"]
    assert types(movement_type=["TRANSFER", "RECEIPT"], product_id=world.steel["id"]) == ["TRANSFER", "RECEIPT"]
    assert types(warehouse_id=world.second["id"]) == ["TRANSFER"]  # destination side
    assert types(location_id=world.rack_a["id"]) == ["TRANSFER", "RECEIPT"]  # either side
    assert types(category_id=world.other_category["id"]) == ["RECEIPT"]
    assert types(q=receipt["reference"]) == ["RECEIPT"]
    today = date.today()
    assert len(types(date_from=str(today - timedelta(days=1)), date_to=str(today + timedelta(days=1)))) == 3
    assert types(date_from=str(today + timedelta(days=2))) == []


def test_stock_is_read_only(inv, client, staff):
    assert client.post("/api/stock", json={}, headers=staff).status_code == 405
    assert client.get("/api/stock").status_code == 401
    assert client.get("/api/stock-movements").status_code == 401


def test_failed_movement_insert_rolls_back_stock_and_status(inv, world, monkeypatch):
    """Stock update succeeds but writing its movement fails -> nothing is kept."""
    inv.receive(world.chair["id"], world.rack_a["id"], 100)
    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 20)])
    inv.prepare_delivery(delivery["id"])

    def broken_record(self, *args, **kwargs):
        raise RuntimeError("simulated movement insert failure")

    monkeypatch.setattr(stock_services.StockOperation, "_record", broken_record)
    with pytest.raises(RuntimeError, match="simulated"):
        inv.post(f"/deliveries/{delivery['id']}/validate")
    monkeypatch.undo()

    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 100
    assert inv.get(f"/deliveries/{delivery['id']}").json()["status"] == "READY"
    assert inv.movements(reference_type="DELIVERY") == []
    # The order can still be validated normally afterwards.
    assert inv.action(f"/deliveries/{delivery['id']}/validate")["status"] == "DONE"
    assert inv.stock(world.chair["id"], world.rack_a["id"]) == 80
