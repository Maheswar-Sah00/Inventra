def rows(inv, **params):
    response = inv.get("/stock-availability", **params)
    assert response.status_code == 200, response.text
    return [(r["product"]["sku"], r["location"]["code"], r["quantity"], r["status"]) for r in response.json()["items"]]


def test_statuses_and_ordering(inv, md, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 75)
    inv.receive(world.chair["id"], world.rack_b["id"], 3)
    md.rule(product_id=world.steel["id"], location_id=world.rack_a["id"], minimum_quantity=80, target_quantity=200)
    md.rule(product_id=world.chair["id"], location_id=world.rack_c["id"], minimum_quantity=2, target_quantity=10)

    # Most urgent first: out of stock (rule, never stocked), low stock, in stock (no rule).
    assert rows(inv) == [
        ("CHR", "RACK-C", 0, "OUT_OF_STOCK"),
        ("STL", "RACK-A", 75, "LOW_STOCK"),
        ("CHR", "RACK-B", 3, "IN_STOCK"),
    ]
    body = inv.get("/stock-availability").json()["items"][1]
    assert body["minimum_quantity"] == 80 and body["target_quantity"] == 200
    assert body["category"]["name"] == "Raw Materials"
    assert body["location"]["warehouse"]["code"] == "MAIN"
    assert body["product"]["unit_of_measure"]["symbol"] == "pc"


def test_emptied_position_is_out_of_stock(inv, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 5)
    doc = inv.create("/adjustments", {"location_id": world.rack_a["id"], "reason": "Lost",
                                      "items": [{"product_id": world.steel["id"], "counted_quantity": 0}]})
    inv.action(f"/adjustments/{doc['id']}/validate")
    assert rows(inv) == [("STL", "RACK-A", 0, "OUT_OF_STOCK")]


def test_filters(inv, md, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    inv.receive(world.steel["id"], world.rack_c["id"], 1)
    inv.receive(world.chair["id"], world.rack_b["id"], 4)
    md.rule(product_id=world.steel["id"], location_id=world.rack_c["id"], minimum_quantity=5, target_quantity=10)

    assert rows(inv, warehouse_id=world.second["id"]) == [("STL", "RACK-C", 1, "LOW_STOCK")]
    assert rows(inv, location_id=world.rack_b["id"]) == [("CHR", "RACK-B", 4, "IN_STOCK")]
    assert [r[0] for r in rows(inv, category_id=world.category["id"])] == ["STL", "STL"]
    assert rows(inv, q="chr") == [("CHR", "RACK-B", 4, "IN_STOCK")]
    assert rows(inv, product_id=world.chair["id"]) == [("CHR", "RACK-B", 4, "IN_STOCK")]
    assert rows(inv, status="LOW_STOCK") == [("STL", "RACK-C", 1, "LOW_STOCK")]
    assert len(rows(inv, status=["IN_STOCK", "LOW_STOCK"])) == 3
    assert inv.get("/stock-availability", status="LOW").status_code == 422
    assert inv.get("/stock-availability", warehouse_id=9999).status_code == 422


def test_inactive_products_and_rules_are_ignored(inv, md, world, client, manager):
    inv.receive(world.chair["id"], world.rack_a["id"], 1)
    rule = md.rule(product_id=world.chair["id"], location_id=world.rack_a["id"], minimum_quantity=5, target_quantity=9)
    assert rows(inv) == [("CHR", "RACK-A", 1, "LOW_STOCK")]
    client.patch(f"/api/reorder-rules/{rule['id']}", headers=manager, json={"is_active": False})
    assert rows(inv) == [("CHR", "RACK-A", 1, "IN_STOCK")]
    client.patch(f"/api/products/{world.chair['id']}", headers=manager, json={"is_active": False})
    assert rows(inv) == []


def test_pagination(inv, world, md):
    for location in (world.rack_a, world.rack_b, world.rack_c):
        inv.receive(world.steel["id"], location["id"], 1)
    first = inv.get("/stock-availability", limit=2).json()
    second = inv.get("/stock-availability", limit=2, offset=2).json()
    assert first["total"] == 3 and len(first["items"]) == 2 and len(second["items"]) == 1


def test_availability_matches_dashboard_counts(inv, md, world):
    """The KPI and the list it links to must agree."""
    inv.receive(world.steel["id"], world.rack_a["id"], 2)
    md.rule(product_id=world.steel["id"], location_id=world.rack_a["id"], minimum_quantity=5, target_quantity=9)
    md.rule(product_id=world.chair["id"], location_id=world.rack_b["id"], minimum_quantity=1, target_quantity=9)
    body = inv.get("/dashboard/summary").json()
    assert body["low_stock_items"] == inv.get("/stock-availability", status="LOW_STOCK").json()["total"] == 1
    assert body["out_of_stock_items"] == inv.get("/stock-availability", status="OUT_OF_STOCK").json()["total"] == 1
