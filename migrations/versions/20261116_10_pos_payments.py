"""Immutable per-order manual tender metadata; no second financial order ledger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261116_10"
down_revision = "20261116_09"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("manual_tender_receipts"):
        op.create_table(
            "manual_tender_receipts",
            sa.Column("order_id", sa.String(36),
                      sa.ForeignKey("sale_orders.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("branch_id", sa.String(36),
                      sa.ForeignKey("branches.id"), nullable=False),
            sa.Column("method", sa.String(24), nullable=False),
            sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
            sa.Column("cash_received_vnd", sa.BigInteger(), nullable=True),
            sa.Column("change_vnd", sa.BigInteger(), nullable=False,
                      server_default="0"),
            sa.Column("transfer_reference", sa.String(120), nullable=False,
                      server_default=""),
            sa.Column("request_id", sa.String(80), nullable=False),
            sa.Column("confirmed_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("provider_verified", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("business_id", "request_id",
                                name="uq_tender_tenant_request"),
        )
    existing={x["name"] for x in inspect(bind).get_indexes("manual_tender_receipts")}
    if "ix_manual_tender_receipts_business_id" not in existing:
        op.create_index("ix_manual_tender_receipts_business_id",
                        "manual_tender_receipts", ["business_id"])


def downgrade():
    raise RuntimeError("Cannot silently drop immutable cashier confirmation history")
