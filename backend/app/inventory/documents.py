"""Lifecycle shared by receipts, delivery orders, internal transfers and inventory adjustments.

Statuses: DRAFT -> (confirm) -> WAITING | READY -> (validate) -> DONE, and any open status -> CANCELED.
Only validation changes stock. DONE and CANCELED are final.

Every state change is an atomic compare-and-set on the document row
(UPDATE ... WHERE id = :id AND status IN (...)). It is always the first write of its transaction,
so two concurrent requests cannot both act on the same document: the loser sees zero updated rows.
This is what makes validation idempotent and safe to retry.
"""

import enum
from datetime import date, datetime
from typing import Any, ClassVar

from fastapi import HTTPException, status
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Select, String, exists, or_, select, update
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column, relationship

from app.core.database import TimestampMixin, utcnow
from app.core.pagination import contains
from app.inventory.services import DocumentRef, InsufficientStock
from app.products.models import Product
from app.users.models import User


class DocumentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    WAITING = "WAITING"  # confirmed, but not enough stock at the source yet
    READY = "READY"  # confirmed and ready to be processed
    DONE = "DONE"  # validated: stock has been updated
    CANCELED = "CANCELED"


OPEN_STATUSES = (DocumentStatus.DRAFT, DocumentStatus.WAITING, DocumentStatus.READY)


class DocumentMixin(TimestampMixin):
    """Columns common to every inventory document. Subclasses set REFERENCE_PREFIX and LABEL."""

    REFERENCE_PREFIX: ClassVar[str]  # e.g. "REC"
    LABEL: ClassVar[str]  # human name used in messages, e.g. "receipt"
    MOVEMENT_REFERENCE_TYPE: ClassVar[str]  # e.g. "RECEIPT"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-readable number such as REC-000001, derived from the id when the document is created.
    reference: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, length=16),
        default=DocumentStatus.DRAFT,
        index=True,
        nullable=False,
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def created_by_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    @declared_attr
    def validated_by_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)

    @declared_attr
    def created_by(cls) -> Mapped[User]:
        return relationship(User, foreign_keys=f"{cls.__name__}.created_by_id", lazy="joined")

    @declared_attr
    def validated_by(cls) -> Mapped[User | None]:
        return relationship(User, foreign_keys=f"{cls.__name__}.validated_by_id", lazy="joined")

    @property
    def document_ref(self) -> DocumentRef:
        return DocumentRef(self.MOVEMENT_REFERENCE_TYPE, self.id, self.reference or "")


# --- Errors -------------------------------------------------------------------------------------


def status_conflict(document: DocumentMixin, action: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        f"Cannot {action} {document.reference}: the {document.LABEL} is {document.status.value}.",
    )


def shortage_conflict(error: InsufficientStock) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(error))


def line_error(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)


# --- Creation and references --------------------------------------------------------------------


def assign_reference(db: Session, document: DocumentMixin) -> None:
    """Flush to obtain the id, then derive the unique reference number from it."""
    db.flush()
    document.reference = f"{document.REFERENCE_PREFIX}-{document.id:06d}"


def check_products(db: Session, product_ids: list[int]) -> dict[int, Product]:
    """All products must exist and be active. Returns them by id."""
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids))).unique()}
    for index, product_id in enumerate(product_ids, start=1):
        product = products.get(product_id)
        if product is None:
            raise line_error(f"Line {index}: product {product_id} not found")
        if not product.is_active:
            raise line_error(f"Line {index}: product {product.sku} is inactive")
    return products


# --- State transitions --------------------------------------------------------------------------


def claim(
    db: Session,
    document: DocumentMixin,
    from_statuses: tuple[DocumentStatus, ...],
    conditions: tuple = (),
    **values: Any,
) -> bool:
    """Atomically update the document only if its status is still one of `from_statuses`
    (and any extra `conditions` hold). Returns False if another request changed it first."""
    model = type(document)
    result = db.execute(
        update(model)
        .where(model.id == document.id, model.status.in_(from_statuses), *conditions)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def replace_items(db: Session, document, item_class, lines: list[dict]) -> None:
    """Replace all lines. Old lines are deleted first so a product can be re-added without
    tripping the one-line-per-product unique constraint."""
    document.items.clear()
    db.flush()
    document.items.extend(item_class(**line) for line in lines)


def begin_edit(db: Session, document: DocumentMixin, **extra: Any) -> None:
    """Editing is allowed while open; a confirmed document goes back to DRAFT and must be re-confirmed."""
    if document.status not in OPEN_STATUSES or not claim(
        db, document, OPEN_STATUSES, status=DocumentStatus.DRAFT, **extra
    ):
        db.rollback()
        db.refresh(document)
        raise status_conflict(document, "edit")
    document.status = DocumentStatus.DRAFT
    for key, value in extra.items():
        setattr(document, key, value)


def begin_validation(
    db: Session, document: DocumentMixin, user: User, allowed: tuple[DocumentStatus, ...] = OPEN_STATUSES
) -> bool:
    """Mark the document DONE as the first write of the transaction.

    Returns False when it is already DONE (idempotent repeat: the caller must not touch stock).
    """
    if document.status == DocumentStatus.DONE:
        return False
    if document.status not in allowed or not claim(
        db, document, allowed, status=DocumentStatus.DONE, validated_at=utcnow(), validated_by_id=user.id
    ):
        db.rollback()
        db.refresh(document)
        if document.status == DocumentStatus.DONE:
            return False
        raise status_conflict(document, "validate")
    return True


def cancel(db: Session, document: DocumentMixin) -> DocumentMixin:
    if document.status == DocumentStatus.CANCELED:
        return document
    if document.status not in OPEN_STATUSES or not claim(
        db, document, OPEN_STATUSES, status=DocumentStatus.CANCELED, canceled_at=utcnow()
    ):
        db.rollback()
        db.refresh(document)
        if document.status == DocumentStatus.CANCELED:
            return document
        raise status_conflict(document, "cancel")
    db.commit()
    db.refresh(document)
    return document


def set_confirmed_status(db: Session, document: DocumentMixin, new_status: DocumentStatus) -> DocumentMixin:
    """DRAFT/WAITING -> READY or WAITING. READY is returned unchanged."""
    if document.status == DocumentStatus.READY:
        return document
    allowed = (DocumentStatus.DRAFT, DocumentStatus.WAITING)
    if document.status not in allowed or not claim(db, document, allowed, status=new_status):
        db.rollback()
        db.refresh(document)
        raise status_conflict(document, "confirm")
    db.commit()
    db.refresh(document)
    return document


def run_validation(db: Session, document: DocumentMixin, apply) -> None:
    """Run `apply()` (stock changes) and commit, or roll everything back, including the DONE status."""
    try:
        apply()
        db.commit()
    except InsufficientStock as error:
        db.rollback()
        raise shortage_conflict(error) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.expire_all()
    db.refresh(document)


# --- Listing ------------------------------------------------------------------------------------


def filter_documents(
    statement: Select,
    model,
    item_document_column,
    item_product_column,
    *,
    statuses: list[DocumentStatus] | None,
    q: str | None,
    search_columns: tuple = (),
    product_id: int | None,
    category_id: int | None,
) -> Select:
    """Filters shared by all document lists; newest first."""
    if statuses:
        statement = statement.where(model.status.in_(statuses))
    if q:
        statement = statement.where(or_(contains(model.reference, q), *(contains(c, q) for c in search_columns)))
    if product_id is not None:
        statement = statement.where(
            exists().where(item_document_column == model.id, item_product_column == product_id)
        )
    if category_id is not None:
        statement = statement.where(
            exists().where(
                item_document_column == model.id,
                item_product_column == Product.id,
                Product.category_id == category_id,
            )
        )
    return statement.order_by(model.id.desc())
