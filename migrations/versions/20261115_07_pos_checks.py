"""V7 additive POS check metadata + audit-safe idempotent ticket mutations."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "20261115_07"
down_revision = "20261115_06"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("pos_check_meta"):
        op.create_table(
            "pos_check_meta",
            sa.Column("order_id", sa.String(36),
                      sa.ForeignKey("sale_orders.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("subtotal_vnd", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("discount_vnd", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("tip_vnd", sa.BigInteger(), nullable=False, server_default="0"),
        )
    if not inspect(bind).has_table("pos_check_mutations"):
        op.create_table(
            "pos_check_mutations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("order_id", sa.String(36),
                      sa.ForeignKey("sale_orders.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("request_id", sa.String(80), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("response", sa.JSON(), nullable=False),
            sa.UniqueConstraint("business_id", "request_id",
                                name="uq_pos_mutation_tenant_request"),
        )


def downgrade():
    raise RuntimeError("Do not automatically delete POS edit audit metadata")
