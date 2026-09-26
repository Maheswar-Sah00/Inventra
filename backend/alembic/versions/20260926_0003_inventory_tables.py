"""inventory: stock, stock_movements, receipts, deliveries, transfers, adjustments (+ item tables)

Revision ID: 0003_inventory
Revises: 0002_master_data
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0003_inventory'
down_revision: Union[str, None] = '0002_master_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('adjustments',
    sa.Column('location_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'WAITING', 'READY', 'DONE', 'CANCELED', name='document_status', native_enum=False, length=16), nullable=False),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('validated_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_adjustments_created_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], name=op.f('fk_adjustments_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'], name=op.f('fk_adjustments_validated_by_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_adjustments')),
    sa.UniqueConstraint('reference', name=op.f('uq_adjustments_reference'))
    )
    op.create_index(op.f('ix_adjustments_location_id'), 'adjustments', ['location_id'], unique=False)
    op.create_index(op.f('ix_adjustments_status'), 'adjustments', ['status'], unique=False)

    op.create_table('deliveries',
    sa.Column('customer_name', sa.String(length=100), nullable=True),
    sa.Column('source_location_id', sa.Integer(), nullable=False),
    sa.Column('picked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('picked_by_id', sa.Integer(), nullable=True),
    sa.Column('packed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('packed_by_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'WAITING', 'READY', 'DONE', 'CANCELED', name='document_status', native_enum=False, length=16), nullable=False),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('validated_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_deliveries_created_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['packed_by_id'], ['users.id'], name=op.f('fk_deliveries_packed_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['picked_by_id'], ['users.id'], name=op.f('fk_deliveries_picked_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_location_id'], ['locations.id'], name=op.f('fk_deliveries_source_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'], name=op.f('fk_deliveries_validated_by_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_deliveries')),
    sa.UniqueConstraint('reference', name=op.f('uq_deliveries_reference'))
    )
    op.create_index(op.f('ix_deliveries_source_location_id'), 'deliveries', ['source_location_id'], unique=False)
    op.create_index(op.f('ix_deliveries_status'), 'deliveries', ['status'], unique=False)

    op.create_table('receipts',
    sa.Column('supplier_name', sa.String(length=100), nullable=False),
    sa.Column('supplier_reference', sa.String(length=100), nullable=True),
    sa.Column('destination_location_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'WAITING', 'READY', 'DONE', 'CANCELED', name='document_status', native_enum=False, length=16), nullable=False),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('validated_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_receipts_created_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], name=op.f('fk_receipts_destination_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'], name=op.f('fk_receipts_validated_by_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_receipts')),
    sa.UniqueConstraint('reference', name=op.f('uq_receipts_reference'))
    )
    op.create_index(op.f('ix_receipts_destination_location_id'), 'receipts', ['destination_location_id'], unique=False)
    op.create_index(op.f('ix_receipts_status'), 'receipts', ['status'], unique=False)

    op.create_table('transfers',
    sa.Column('source_location_id', sa.Integer(), nullable=False),
    sa.Column('destination_location_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'WAITING', 'READY', 'DONE', 'CANCELED', name='document_status', native_enum=False, length=16), nullable=False),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('validated_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('source_location_id <> destination_location_id', name=op.f('ck_transfers_distinct_locations')),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_transfers_created_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], name=op.f('fk_transfers_destination_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_location_id'], ['locations.id'], name=op.f('fk_transfers_source_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['validated_by_id'], ['users.id'], name=op.f('fk_transfers_validated_by_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_transfers')),
    sa.UniqueConstraint('reference', name=op.f('uq_transfers_reference'))
    )
    op.create_index(op.f('ix_transfers_destination_location_id'), 'transfers', ['destination_location_id'], unique=False)
    op.create_index(op.f('ix_transfers_source_location_id'), 'transfers', ['source_location_id'], unique=False)
    op.create_index(op.f('ix_transfers_status'), 'transfers', ['status'], unique=False)

    op.create_table('adjustment_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('adjustment_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('counted_quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.Column('recorded_quantity', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.Column('difference', sa.Numeric(precision=14, scale=3), nullable=True),
    sa.CheckConstraint('counted_quantity >= 0', name=op.f('ck_adjustment_items_counted_quantity_non_negative')),
    sa.ForeignKeyConstraint(['adjustment_id'], ['adjustments.id'], name=op.f('fk_adjustment_items_adjustment_id_adjustments'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_adjustment_items_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_adjustment_items')),
    sa.UniqueConstraint('adjustment_id', 'product_id', name='uq_adjustment_items_adjustment_id_product_id')
    )
    op.create_index(op.f('ix_adjustment_items_adjustment_id'), 'adjustment_items', ['adjustment_id'], unique=False)
    op.create_index(op.f('ix_adjustment_items_product_id'), 'adjustment_items', ['product_id'], unique=False)

    op.create_table('delivery_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('delivery_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_delivery_items_quantity_positive')),
    sa.ForeignKeyConstraint(['delivery_id'], ['deliveries.id'], name=op.f('fk_delivery_items_delivery_id_deliveries'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_delivery_items_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_delivery_items')),
    sa.UniqueConstraint('delivery_id', 'product_id', name='uq_delivery_items_delivery_id_product_id')
    )
    op.create_index(op.f('ix_delivery_items_delivery_id'), 'delivery_items', ['delivery_id'], unique=False)
    op.create_index(op.f('ix_delivery_items_product_id'), 'delivery_items', ['product_id'], unique=False)

    op.create_table('receipt_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('receipt_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_receipt_items_quantity_positive')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_receipt_items_product_id_products'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], name=op.f('fk_receipt_items_receipt_id_receipts'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_receipt_items')),
    sa.UniqueConstraint('receipt_id', 'product_id', name='uq_receipt_items_receipt_id_product_id')
    )
    op.create_index(op.f('ix_receipt_items_product_id'), 'receipt_items', ['product_id'], unique=False)
    op.create_index(op.f('ix_receipt_items_receipt_id'), 'receipt_items', ['receipt_id'], unique=False)

    op.create_table('stock',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('location_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity >= 0', name=op.f('ck_stock_quantity_non_negative')),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], name=op.f('fk_stock_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_stock_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock')),
    sa.UniqueConstraint('product_id', 'location_id', name='uq_stock_product_id_location_id')
    )
    op.create_index(op.f('ix_stock_location_id'), 'stock', ['location_id'], unique=False)
    op.create_index(op.f('ix_stock_product_id'), 'stock', ['product_id'], unique=False)

    op.create_table('stock_movements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('movement_type', sa.Enum('INITIAL_STOCK', 'RECEIPT', 'DELIVERY', 'TRANSFER', 'ADJUSTMENT', name='movement_type', native_enum=False, length=20), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.Column('source_location_id', sa.Integer(), nullable=True),
    sa.Column('destination_location_id', sa.Integer(), nullable=True),
    sa.Column('reference_type', sa.String(length=20), nullable=False),
    sa.Column('reference_id', sa.Integer(), nullable=False),
    sa.Column('reference_number', sa.String(length=64), nullable=False),
    sa.Column('performed_by_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('quantity <> 0', name=op.f('ck_stock_movements_quantity_not_zero')),
    sa.CheckConstraint('source_location_id IS NOT NULL OR destination_location_id IS NOT NULL', name=op.f('ck_stock_movements_has_location')),
    sa.ForeignKeyConstraint(['destination_location_id'], ['locations.id'], name=op.f('fk_stock_movements_destination_location_id_locations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['performed_by_id'], ['users.id'], name=op.f('fk_stock_movements_performed_by_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_stock_movements_product_id_products'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_location_id'], ['locations.id'], name=op.f('fk_stock_movements_source_location_id_locations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_movements'))
    )
    op.create_index(op.f('ix_stock_movements_created_at'), 'stock_movements', ['created_at'], unique=False)
    op.create_index(op.f('ix_stock_movements_destination_location_id'), 'stock_movements', ['destination_location_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_movement_type'), 'stock_movements', ['movement_type'], unique=False)
    op.create_index(op.f('ix_stock_movements_product_id'), 'stock_movements', ['product_id'], unique=False)
    op.create_index('ix_stock_movements_reference', 'stock_movements', ['reference_type', 'reference_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_source_location_id'), 'stock_movements', ['source_location_id'], unique=False)

    op.create_table('transfer_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('transfer_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_transfer_items_quantity_positive')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_transfer_items_product_id_products'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], name=op.f('fk_transfer_items_transfer_id_transfers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_transfer_items')),
    sa.UniqueConstraint('transfer_id', 'product_id', name='uq_transfer_items_transfer_id_product_id')
    )
    op.create_index(op.f('ix_transfer_items_product_id'), 'transfer_items', ['product_id'], unique=False)
    op.create_index(op.f('ix_transfer_items_transfer_id'), 'transfer_items', ['transfer_id'], unique=False)



def downgrade() -> None:
    op.drop_index(op.f('ix_transfer_items_transfer_id'), table_name='transfer_items')
    op.drop_index(op.f('ix_transfer_items_product_id'), table_name='transfer_items')

    op.drop_table('transfer_items')
    op.drop_index(op.f('ix_stock_movements_source_location_id'), table_name='stock_movements')
    op.drop_index('ix_stock_movements_reference', table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_product_id'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_movement_type'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_destination_location_id'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_created_at'), table_name='stock_movements')

    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_stock_product_id'), table_name='stock')
    op.drop_index(op.f('ix_stock_location_id'), table_name='stock')

    op.drop_table('stock')
    op.drop_index(op.f('ix_receipt_items_receipt_id'), table_name='receipt_items')
    op.drop_index(op.f('ix_receipt_items_product_id'), table_name='receipt_items')

    op.drop_table('receipt_items')
    op.drop_index(op.f('ix_delivery_items_product_id'), table_name='delivery_items')
    op.drop_index(op.f('ix_delivery_items_delivery_id'), table_name='delivery_items')

    op.drop_table('delivery_items')
    op.drop_index(op.f('ix_adjustment_items_product_id'), table_name='adjustment_items')
    op.drop_index(op.f('ix_adjustment_items_adjustment_id'), table_name='adjustment_items')

    op.drop_table('adjustment_items')
    op.drop_index(op.f('ix_transfers_status'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_source_location_id'), table_name='transfers')
    op.drop_index(op.f('ix_transfers_destination_location_id'), table_name='transfers')

    op.drop_table('transfers')
    op.drop_index(op.f('ix_receipts_status'), table_name='receipts')
    op.drop_index(op.f('ix_receipts_destination_location_id'), table_name='receipts')

    op.drop_table('receipts')
    op.drop_index(op.f('ix_deliveries_status'), table_name='deliveries')
    op.drop_index(op.f('ix_deliveries_source_location_id'), table_name='deliveries')

    op.drop_table('deliveries')
    op.drop_index(op.f('ix_adjustments_status'), table_name='adjustments')
    op.drop_index(op.f('ix_adjustments_location_id'), table_name='adjustments')

    op.drop_table('adjustments')
