from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.core.crud import (
    apply_changes,
    commit_or_conflict,
    delete_or_conflict,
    ensure_unique,
    get_or_404,
    get_reference,
)
from app.core.errors import conflict, field_error
from app.core.pagination import Page, PageParams, contains, paginate
from app.locations.services import get_usable_location
from app.products.events import dispatch_initial_stock
from app.products.models import Product
from app.products.schemas import ProductCreate, ProductOut, ProductUpdate
from app.units.models import UnitOfMeasure
from app.users.models import User

DUPLICATE_SKU = "A product with this SKU already exists"


def list_products(
    db: Session,
    page: PageParams,
    *,
    q: str | None,
    category_id: int | None,
    unit_of_measure_id: int | None,
    is_active: bool | None,
) -> Page:
    statement = select(Product)
    if q:
        statement = statement.where(or_(contains(Product.name, q), contains(Product.sku, q)))
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if unit_of_measure_id is not None:
        statement = statement.where(Product.unit_of_measure_id == unit_of_measure_id)
    if is_active is not None:
        statement = statement.where(Product.is_active == is_active)
    return paginate(db, statement.order_by(Product.name, Product.id), page, ProductOut)


def get_product(db: Session, product_id: int) -> Product:
    return get_or_404(db, Product, product_id, "Product")


def create_product(db: Session, data: ProductCreate, created_by: User) -> Product:
    ensure_unique(db, Product.sku, data.sku, field="sku", message=DUPLICATE_SKU)
    get_reference(db, Category, data.category_id, field="category_id", label="Category")
    get_reference(db, UnitOfMeasure, data.unit_of_measure_id, field="unit_of_measure_id", label="Unit of measure")

    initial_location_id = None
    if data.initial_stock > 0:
        if data.initial_location_id is None:
            raise field_error("initial_location_id", "Choose the location that holds the initial stock")
        initial_location_id = get_usable_location(db, data.initial_location_id, field="initial_location_id").id

    product = Product(**data.model_dump(exclude={"initial_location_id"}), initial_location_id=initial_location_id)
    db.add(product)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict("sku", DUPLICATE_SKU) from None
    try:
        if product.initial_stock > 0:
            dispatch_initial_stock(db, product, created_by)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, data: ProductUpdate) -> Product:
    changes = data.changes()
    if "sku" in changes:
        ensure_unique(db, Product.sku, changes["sku"], field="sku", message=DUPLICATE_SKU, exclude_id=product.id)
    # Only a newly chosen category/unit must be active; existing links to archived ones stay valid.
    if changes.get("category_id", product.category_id) != product.category_id:
        get_reference(db, Category, changes["category_id"], field="category_id", label="Category")
    if changes.get("unit_of_measure_id", product.unit_of_measure_id) != product.unit_of_measure_id:
        get_reference(db, UnitOfMeasure, changes["unit_of_measure_id"], field="unit_of_measure_id", label="Unit of measure")
    apply_changes(product, changes)
    commit_or_conflict(db, "sku", DUPLICATE_SKU)
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    """Only succeeds while nothing (e.g. stock moves) references the product; otherwise deactivate it."""
    delete_or_conflict(db, product, "product")
