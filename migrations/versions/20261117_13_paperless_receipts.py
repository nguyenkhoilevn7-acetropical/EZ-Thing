"""Paperless receipt ownership, anonymous wallets and optional Google member sessions.

Revision ID: 20261117_13
Revises: 20261116_12
These are reference tables; sale_orders, sale_order_items and the existing loyalty
IndustryWorkItem ledger remain authoritative.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261117_13"
down_revision = "20261116_12"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    present = set(inspect(bind).get_table_names())
    if "receipt_guest_wallets" not in present:
        op.create_table(
            "receipt_guest_wallets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("secret_hash", sa.String(64), unique=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "receipt_members" not in present:
        op.create_table(
            "receipt_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("google_sub", sa.String(255), unique=True, nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("phone", sa.String(30), nullable=False),
            sa.Column("member_code", sa.String(32), unique=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "receipt_member_sessions" not in present:
        op.create_table(
            "receipt_member_sessions",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("member_id", sa.String(36), sa.ForeignKey("receipt_members.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "receipt_member_customers" not in present:
        op.create_table(
            "receipt_member_customers",
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("member_id", sa.String(36), sa.ForeignKey("receipt_members.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.UniqueConstraint("business_id", "customer_id"),
        )
    if "receipt_claim_tokens" not in present:
        op.create_table(
            "receipt_claim_tokens",
            sa.Column("order_id", sa.String(36), sa.ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("secret_hash", sa.String(64), unique=True, nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "receipt_wallet_orders" not in present:
        op.create_table(
            "receipt_wallet_orders",
            sa.Column("order_id", sa.String(36), sa.ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("wallet_id", sa.String(36), sa.ForeignKey("receipt_guest_wallets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("member_id", sa.String(36), sa.ForeignKey("receipt_members.id", ondelete="SET NULL"), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    for table in ("receipt_wallet_orders", "receipt_claim_tokens",
                  "receipt_member_customers", "receipt_member_sessions",
                  "receipt_members", "receipt_guest_wallets"):
        if table in inspect(op.get_bind()).get_table_names():
            op.drop_table(table)
