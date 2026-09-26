"""Dashboard KPIs computed from real documents and stock created through the inventory APIs."""

import pytest

ZERO_KPIS = {
    "total_products_in_stock": 0,
    "low_stock_items": 0,
    "out_of_stock_items": 0,
    "pending_receipts": 0,
    "pending_deliveries": 0,
    "scheduled_transfers": 0,
}


def summary(inv, **params):
    response = inv.get("/dashboard/summary", **params)
    assert response.status_code == 200, response.text
    return response.json()


def kpis(body):
    return {key: body[key] for key in ZERO_KPIS}


def receipt(inv, location, product, quantity, supplier="Acme"):
    return inv.create(
        "/receipts",
        {"supplier_name": supplier, "destination_location_id": location["id"], "items": [{"product_id": product["id"], "quantity": quantity}]},
    )


def test_zero_data(inv):
    body = summary(inv)
    assert kpis(body) == ZERO_KPIS
    assert body["counted_statuses"] == ["DRAFT", "WAITING", "READY"]
    assert [d["document_type"] for d in body["documents"]] == ["RECEIPT", "DELIVERY", "TRANSFER", "ADJUSTMENT"]
    assert all(d["total"] == 0 for d in body["documents"])


def test_kpi_calculations(inv, md, world):
    # Stock: steel 100 @ A, chair 3 @ B (rule min 5 -> low), steel rule @ C with no stock (-> out).
    inv.receive(world.steel["id"], world.rack_a["id"], 100)
    inv.receive(world.chair["id"], world.rack_b["id"], 3)
    md.rule(product_id=world.chair["id"], location_id=world.rack_b["id"], minimum_quantity=5, target_quantity=20)
    md.rule(product_id=world.steel["id"], location_id=world.rack_c["id"], minimum_quantity=1, target_quantity=10)
    md.rule(product_id=world.steel["id"], location_id=world.rack_a["id"], minimum_quantity=10, target_quantity=200)

    # Documents: 2 pending receipts (+2 done from receive()), 1 canceled; 1 pending delivery; 1 done, 1 pending transfer.
    receipt(inv, world.rack_a, world.steel, 5)
    ready = receipt(inv, world.rack_a, world.steel, 5)
    inv.action(f"/receipts/{ready['id']}/confirm")
    canceled = receipt(inv, world.rack_a, world.steel, 5)
    inv.action(f"/receipts/{canceled['id']}/cancel")
    inv.delivery(world.rack_a["id"], [(world.steel["id"], 10)])
    moved = inv.create("/transfers", {"source_location_id": world.rack_a["id"], "destination_location_id": world.rack_c["id"],
                                      "items": [{"product_id": world.steel["id"], "quantity": 1}]})
    inv.create("/transfers", {"source_location_id": world.rack_a["id"], "destination_location_id": world.rack_b["id"],
                              "items": [{"product_id": world.steel["id"], "quantity": 1}]})

    body = summary(inv)
    assert kpis(body) == {
        "total_products_in_stock": 2,
        "low_stock_items": 1,
        "out_of_stock_items": 1,
        "pending_receipts": 2,
        "pending_deliveries": 1,
        "scheduled_transfers": 2,
    }
    receipts = next(d for d in body["documents"] if d["document_type"] == "RECEIPT")
    assert receipts["counts"] == {"DRAFT": 1, "WAITING": 0, "READY": 1, "DONE": 2, "CANCELED": 1}
    assert receipts["total"] == 5

    # Completing the transfer moves steel into Rack C: out-of-stock clears, one fewer scheduled transfer.
    inv.action(f"/transfers/{moved['id']}/validate")
    assert kpis(summary(inv)) == {
        "total_products_in_stock": 2,
        "low_stock_items": 2,  # Rack C now holds 1 = its minimum
        "out_of_stock_items": 0,
        "pending_receipts": 2,
        "pending_deliveries": 1,
        "scheduled_transfers": 1,
    }


def test_completing_documents_updates_dashboard(inv, world):
    pending = receipt(inv, world.rack_a, world.chair, 10)
    assert kpis(summary(inv))["pending_receipts"] == 1
    assert kpis(summary(inv))["total_products_in_stock"] == 0

    inv.action(f"/receipts/{pending['id']}/validate")
    after_receipt = kpis(summary(inv))
    assert after_receipt["pending_receipts"] == 0 and after_receipt["total_products_in_stock"] == 1

    delivery = inv.delivery(world.rack_a["id"], [(world.chair["id"], 10)])
    assert kpis(summary(inv))["pending_deliveries"] == 1
    inv.prepare_delivery(delivery["id"])
    inv.action(f"/deliveries/{delivery['id']}/validate")
    after_delivery = kpis(summary(inv))
    assert after_delivery["pending_deliveries"] == 0
    assert after_delivery["total_products_in_stock"] == 0
    assert after_delivery["out_of_stock_items"] == 1  # the emptied position


def test_scope_filters(inv, md, world):
    inv.receive(world.steel["id"], world.rack_a["id"], 10)
    inv.receive(world.chair["id"], world.rack_c["id"], 2)
    md.rule(product_id=world.chair["id"], location_id=world.rack_c["id"], minimum_quantity=5, target_quantity=10)
    receipt(inv, world.rack_c, world.chair, 1)
    receipt(inv, world.rack_a, world.steel, 1)
    inv.create("/transfers", {"source_location_id": world.rack_a["id"], "destination_location_id": world.rack_c["id"],
                              "items": [{"product_id": world.steel["id"], "quantity": 1}]})

    second = kpis(summary(inv, warehouse_id=world.second["id"]))
    assert second == {"total_products_in_stock": 1, "low_stock_items": 1, "out_of_stock_items": 0,
                      "pending_receipts": 1, "pending_deliveries": 0, "scheduled_transfers": 1}  # transfer lands in WH2

    rack_a = kpis(summary(inv, warehouse_id=world.main["id"], location_id=world.rack_a["id"]))
    assert rack_a == {"total_products_in_stock": 1, "low_stock_items": 0, "out_of_stock_items": 0,
                      "pending_receipts": 1, "pending_deliveries": 0, "scheduled_transfers": 1}

    furniture = kpis(summary(inv, category_id=world.other_category["id"]))  # chairs only
    assert furniture == {"total_products_in_stock": 1, "low_stock_items": 1, "out_of_stock_items": 0,
                         "pending_receipts": 1, "pending_deliveries": 0, "scheduled_transfers": 0}


def test_document_type_and_status_filters(inv, world):
    draft = receipt(inv, world.rack_a, world.steel, 1)
    ready = receipt(inv, world.rack_a, world.steel, 1)
    inv.action(f"/receipts/{ready['id']}/confirm")
    inv.delivery(world.rack_a["id"], [(world.steel["id"], 1)])

    only_receipts = summary(inv, document_type="RECEIPT")
    assert only_receipts["pending_receipts"] == 2
    assert only_receipts["pending_deliveries"] is None and only_receipts["scheduled_transfers"] is None
    assert [d["document_type"] for d in only_receipts["documents"]] == ["RECEIPT"]

    ready_only = summary(inv, status="READY")
    assert ready_only["counted_statuses"] == ["READY"]
    assert (ready_only["pending_receipts"], ready_only["pending_deliveries"]) == (1, 0)
    assert next(d for d in ready_only["documents"] if d["document_type"] == "RECEIPT")["counts"] == {"READY": 1}

    inv.action(f"/receipts/{draft['id']}/validate")
    done = summary(inv, status="DONE", document_type="RECEIPT")
    assert done["pending_receipts"] == 1  # counts the chosen status


@pytest.mark.parametrize(
    "params, field",
    [
        ({"warehouse_id": 9999}, "warehouse_id"),
        ({"location_id": 9999}, "location_id"),
        ({"category_id": 9999}, "category_id"),
    ],
)
def test_unknown_ids_are_rejected(inv, params, field):
    response = inv.get("/dashboard/summary", **params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


def test_location_outside_warehouse_is_rejected(inv, world):
    response = inv.get("/dashboard/summary", warehouse_id=world.second["id"], location_id=world.rack_a["id"])
    assert response.status_code == 422
    assert "does not belong" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("params", [{"document_type": "INVOICE"}, {"status": "PENDING"}, {"warehouse_id": "abc"}, {"warehouse_id": 0}])
def test_malformed_filters_are_rejected(inv, params):
    assert inv.get("/dashboard/summary", **params).status_code == 422


def test_dashboard_requires_authentication_but_any_role(client, manager, staff):
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/stock-availability").status_code == 401
    assert client.get("/api/dashboard/summary", headers=manager).status_code == 200
    assert client.get("/api/dashboard/summary", headers=staff).status_code == 200
