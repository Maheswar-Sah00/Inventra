"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adjustments.routes import router as adjustments_router
from app.auth.routes import router as auth_router
from app.categories.routes import router as categories_router
from app.core.config import get_settings
from app.deliveries.routes import router as deliveries_router
from app.inventory.routes import router as inventory_router
from app.locations.routes import router as locations_router
from app.products.routes import router as products_router
from app.receipts.routes import router as receipts_router
from app.reorder_rules.routes import router as reorder_rules_router
from app.transfers.routes import router as transfers_router
from app.units.routes import router as units_router
from app.users.routes import router as users_router
from app.warehouses.routes import router as warehouses_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get(f"{settings.API_PREFIX}/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Each module registers its router here.
    app.include_router(auth_router, prefix=settings.API_PREFIX)
    app.include_router(users_router, prefix=settings.API_PREFIX)
    # Master data (products & warehouses)
    for router in (
        products_router,
        categories_router,
        units_router,
        warehouses_router,
        locations_router,
        reorder_rules_router,
    ):
        app.include_router(router, prefix=settings.API_PREFIX)
    # Inventory operations & stock engine
    for router in (inventory_router, receipts_router, deliveries_router, transfers_router, adjustments_router):
        app.include_router(router, prefix=settings.API_PREFIX)
    return app


app = create_app()
