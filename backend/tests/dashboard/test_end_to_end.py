"""The brief's inventory flow end to end through the real APIs (no mocked data):

create product, warehouse, location -> receive 100 -> transfer 30 -> deliver 20 -> count 8
-> dashboard, availability and move history all agree with the stock engine.
"""


def test_full_inventory_flow_is_reflected_everywhere(client, manager, md, inv):
    # 1-3. Master data (as an inventory manager).
    category = md.category(name="Raw Materials")
    unit = md.unit(name="Kilogram", symbol="kg")
    warehouse = md.warehouse(name="Main Warehouse", code="MAIN")
    store = md.location(warehouse_id=warehouse["id"], name="Main Store", code="STORE")
    production = md.location(warehouse_id=warehouse["id"], name="Production Rack", code="PROD")
    product = md.product(name="Steel", sku="STEEL-001", category_id=category["id"], unit_of_measure_id=unit["id"])
    pid = product["id"]

    # 4-5. Receive 100.
    received = inv.receive(pid, store["id"], 100)
    assert inv.stock(pid, store["id"]) == 100

    # 6-8. Transfer 30 to the production rack.
    transfer = inv.create("/transfers", {"source_location_id": store["id"], "destination_location_id": production["id"],
                                         "items": [{"product_id": pid, "quantity": 30}]})
    inv.action(f"/transfers/{transfer['id']}/validate")
    assert inv.stock(pid, store["id"]) == 70
    assert inv.stock(pid, production["id"]) == 30

    # 9-10. Deliver 20 from the production rack.
    delivery = inv.delivery(production["id"], [(pid, 20)], customer_name="Globex")
    inv.prepare_delivery(delivery["id"])
    inv.action(f"/deliveries/{delivery['id']}/validate")
    assert inv.stock(pid, production["id"]) == 10

    # 11-12. Physical count at the production rack finds 8.
    adjustment = inv.create("/adjustments", {"location_id": production["id"], "reason": "2 kg damaged",
                                             "items": [{"product_id": pid, "counted_quantity": 8}]})
    inv.action(f"/adjustments/{adjustment['id']}/validate")
    assert inv.stock(pid, production["id"]) == 8

    # 13-14. Dashboard reflects current inventory.
    summary = inv.get("/dashboard/summary").json()
    assert summary["total_products_in_stock"] == 1
    assert (summary["pending_receipts"], summary["pending_deliveries"], summary["scheduled_transfers"]) == (0, 0, 0)
    assert summary["low_stock_items"] == 0 and summary["out_of_stock_items"] == 0
    done = {d["document_type"]: d["counts"]["DONE"] for d in summary["documents"]}
    assert done == {"RECEIPT": 1, "DELIVERY": 1, "TRANSFER": 1, "ADJUSTMENT": 1}

    availability = inv.get("/stock-availability", product_id=pid).json()["items"]
    assert {(r["location"]["code"], r["quantity"], r["status"]) for r in availability} == {
        ("STORE", 70, "IN_STOCK"),
        ("PROD", 8, "IN_STOCK"),
    }
    # A reorder rule turns the production rack into a low-stock alert on the dashboard.
    md.rule(product_id=pid, location_id=production["id"], minimum_quantity=10, target_quantity=40)
    assert inv.get("/dashboard/summary").json()["low_stock_items"] == 1

    # 15-19. Move history (newest first) shows every movement with its document and user.
    history = inv.get("/stock-movements", product_id=pid).json()
    assert history["total"] == 4
    ledger = [(m["movement_type"], m["quantity"], m["source_location_id"], m["destination_location_id"], m["reference_number"])
              for m in reversed(history["items"])]
    assert ledger == [
        ("RECEIPT", 100, None, store["id"], received["reference"]),
        ("TRANSFER", 30, store["id"], production["id"], transfer["reference"]),
        ("DELIVERY", -20, production["id"], None, delivery["reference"]),
        ("ADJUSTMENT", -2, production["id"], None, adjustment["reference"]),
    ]
    assert {m["performed_by"]["name"] for m in history["items"]} == {"Asha Rao"}
    # Replaying the ledger per location matches current stock (consistency check, not how stock is computed).
    per_location: dict[int, float] = {}
    for m in history["items"]:
        if m["source_location_id"]:
            per_location[m["source_location_id"]] = per_location.get(m["source_location_id"], 0) - abs(m["quantity"])
        if m["destination_location_id"]:
            per_location[m["destination_location_id"]] = per_location.get(m["destination_location_id"], 0) + abs(m["quantity"])
    assert per_location == {store["id"]: 70, production["id"]: 8}
    # SKU search on the ledger.
    assert inv.get("/stock-movements", q="STEEL-001").json()["total"] == 4
