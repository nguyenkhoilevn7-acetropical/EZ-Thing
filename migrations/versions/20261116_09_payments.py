"""Additive V8 POS payment accounts, intents and provider-event audit.

Never modifies the authoritative sale_orders / stock movements.
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "20261116_09"
down_revision = "20261116_08"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "merchant_bank_accounts" not in existing:
        op.create_table(
            "merchant_bank_accounts",
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("bank_bin", sa.String(6), nullable=False),
            sa.Column("account_number", sa.String(19), nullable=False),
            sa.Column("account_name", sa.String(100), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
    if "pos_payment_intents" not in existing:
        op.create_table(
            "pos_payment_intents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("branch_id", sa.String(36),
                      sa.ForeignKey("branches.id"), nullable=False),
            sa.Column("order_id", sa.String(36),
                      sa.ForeignKey("sale_orders.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("request_id", sa.String(80), nullable=False),
            sa.Column("method", sa.String(20), nullable=False),
            sa.Column("reference", sa.String(24), nullable=False),
            sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False,
                      server_default="pending"),
            sa.Column("external_transaction_id", sa.String(100)),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("settled_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("business_id", "request_id",
                                name="uq_pos_payment_request"),
            sa.UniqueConstraint("reference", name="uq_pos_payment_reference"),
        )
    if "pos_payment_events" not in existing:
        op.create_table(
            "pos_payment_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("payment_id", sa.String(36),
                      sa.ForeignKey("pos_payment_intents.id")),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("external_id", sa.String(100), nullable=False),
            sa.Column("amount_vnd", sa.BigInteger(), nullable=False),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("payload_sha256", sa.String(64), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("provider", "external_id",
                                name="uq_pos_provider_event"),
        )
    for name, table, cols in (
        ("ix_pos_payment_business_order", "pos_payment_intents",
         ["business_id", "order_id"]),
        ("ix_pos_payment_events_tenant", "pos_payment_events",
         ["business_id", "received_at"]),
    ):
        indexes = {x["name"] for x in inspect(bind).get_indexes(table)}
        if name not in indexes:
            op.create_index(name, table, cols)


def downgrade():
    raise RuntimeError("Payment history must never be silently deleted")
