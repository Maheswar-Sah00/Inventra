"""Integration point between product creation and the inventory module.

The product module records `initial_stock` / `initial_location_id` as entered, but it does not keep
stock. The inventory module owns quantities and registers a handler here to turn the initial
stock into its own records (e.g. an opening stock move):

    from app.products.events import on_initial_stock

    @on_initial_stock
    def create_opening_stock(db, product, created_by):
        db.add(StockMove(product_id=product.id, to_location_id=product.initial_location_id,
                         quantity=product.initial_stock, created_by_id=created_by.id, ...))

Handlers run inside the product-creation transaction, after the product row is flushed (so
`product.id` exists) and before commit. They must not commit. If a handler raises, the product is
not created. Raise an HTTPException to return a specific error to the client.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.products.models import Product
    from app.users.models import User

InitialStockHandler = Callable[[Session, "Product", "User"], None]

_initial_stock_handlers: list[InitialStockHandler] = []


def on_initial_stock(handler: InitialStockHandler) -> InitialStockHandler:
    """Register `handler` to be called when a product is created with initial_stock > 0."""
    if handler not in _initial_stock_handlers:
        _initial_stock_handlers.append(handler)
    return handler


def remove_initial_stock_handler(handler: InitialStockHandler) -> None:
    if handler in _initial_stock_handlers:
        _initial_stock_handlers.remove(handler)


def dispatch_initial_stock(db: Session, product: "Product", created_by: "User") -> None:
    for handler in list(_initial_stock_handlers):
        handler(db, product, created_by)
