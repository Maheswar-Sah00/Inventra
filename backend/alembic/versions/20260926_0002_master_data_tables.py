"""master data: categories, units_of_measure, warehouses, locations, products, reorder_rules

Revision ID: 0002_master_data
Revises: 0001_auth
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_master_data"
down_revision: Union[str, None] = "0001_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )

    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_units_of_measure")),
        sa.UniqueConstraint("name", name=op.f("uq_units_of_measure_name")),
        sa.UniqueConstraint("symbol", name=op.f("uq_units_of_measure_symbol")),
    )

    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("code", name=op.f("uq_warehouses_code")),
        sa.UniqueConstraint("name", name=op.f("uq_warehouses_name")),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], name=op.f("fk_locations_warehouse_id_warehouses"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint("warehouse_id", "code", name="uq_locations_warehouse_id_code"),
        sa.UniqueConstraint("warehouse_id", "name", name="uq_locations_warehouse_id_name"),
    )
    op.create_index(op.f("ix_locations_warehouse_id"), "locations", ["warehouse_id"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("unit_of_measure_id", sa.Integer(), nullable=False),
        sa.Column("initial_stock", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("initial_location_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("initial_stock >= 0", name=op.f("ck_products_initial_stock_non_negative")),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name=op.f("fk_products_category_id_categories"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["unit_of_measure_id"],
            ["units_of_measure.id"],
            name=op.f("fk_products_unit_of_measure_id_units_of_measure"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["initial_location_id"],
            ["locations.id"],
            name=op.f("fk_products_initial_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("sku", name=op.f("uq_products_sku")),
    )
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_unit_of_measure_id"), "products", ["unit_of_measure_id"], unique=False)

    op.create_table(
        "reorder_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("target_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("minimum_quantity >= 0", name=op.f("ck_reorder_rules_minimum_quantity_non_negative")),
        sa.CheckConstraint(
            "target_quantity >= minimum_quantity", name=op.f("ck_reorder_rules_target_not_below_minimum")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_reorder_rules_product_id_products"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], name=op.f("fk_reorder_rules_location_id_locations"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reorder_rules")),
        sa.UniqueConstraint("product_id", "location_id", name="uq_reorder_rules_product_id_location_id"),
    )
    op.create_index(op.f("ix_reorder_rules_product_id"), "reorder_rules", ["product_id"], unique=False)
    op.create_index(op.f("ix_reorder_rules_location_id"), "reorder_rules", ["location_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reorder_rules_location_id"), table_name="reorder_rules")
    op.drop_index(op.f("ix_reorder_rules_product_id"), table_name="reorder_rules")
    op.drop_table("reorder_rules")
    op.drop_index(op.f("ix_products_unit_of_measure_id"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_locations_warehouse_id"), table_name="locations")
    op.drop_table("locations")
    op.drop_table("warehouses")
    op.drop_table("units_of_measure")
    op.drop_table("categories")
