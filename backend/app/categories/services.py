from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories.models import Category
from app.categories.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.core.crud import apply_changes, commit_or_conflict, delete_or_conflict, ensure_unique, get_or_404
from app.core.pagination import Page, PageParams, contains, paginate

DUPLICATE_NAME = "A category with this name already exists"


def list_categories(db: Session, page: PageParams, *, q: str | None, is_active: bool | None) -> Page:
    statement = select(Category)
    if q:
        statement = statement.where(contains(Category.name, q))
    if is_active is not None:
        statement = statement.where(Category.is_active == is_active)
    return paginate(db, statement.order_by(Category.name, Category.id), page, CategoryOut)


def get_category(db: Session, category_id: int) -> Category:
    return get_or_404(db, Category, category_id, "Category")


def create_category(db: Session, data: CategoryCreate) -> Category:
    ensure_unique(db, Category.name, data.name, field="name", message=DUPLICATE_NAME)
    category = Category(**data.model_dump())
    db.add(category)
    commit_or_conflict(db, "name", DUPLICATE_NAME)
    db.refresh(category)
    return category


def update_category(db: Session, category: Category, data: CategoryUpdate) -> Category:
    changes = data.changes()
    if "name" in changes:
        ensure_unique(db, Category.name, changes["name"], field="name", message=DUPLICATE_NAME, exclude_id=category.id)
    apply_changes(category, changes)
    commit_or_conflict(db, "name", DUPLICATE_NAME)
    db.refresh(category)
    return category


def delete_category(db: Session, category: Category) -> None:
    """Only succeeds when no product uses the category; otherwise deactivate it instead."""
    delete_or_conflict(db, category, "category")
