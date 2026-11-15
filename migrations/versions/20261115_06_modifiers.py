"""Additive modifier configuration and immutable per-order-item selection ledger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261115_06"
down_revision = "20261115_05"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("product_modifier_sets"):
        op.create_table(
            "product_modifier_sets",
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("groups", sa.JSON(), nullable=False),
        )
    inspector = inspect(bind)
    if not inspector.has_table("sale_order_item_modifiers"):
        op.create_table(
            "sale_order_item_modifiers",
            sa.Column("item_id", sa.String(36), sa.ForeignKey("sale_order_items.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("selections", sa.JSON(), nullable=False),
        )


def downgrade():
    raise RuntimeError("Do not automatically delete sold option snapshots")
