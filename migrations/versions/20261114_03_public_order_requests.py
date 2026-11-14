"""Public order request queue; no money or inventory moved on guest submit."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision="20261114_03"
down_revision="20261114_02"
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if not inspect(bind).has_table("public_order_requests"):
        op.create_table(
            "public_order_requests",
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("business_id",sa.String(36),
                      sa.ForeignKey("businesses.id",ondelete="CASCADE"),nullable=False),
            sa.Column("request_hash",sa.String(64),nullable=False),
            sa.Column("fingerprint",sa.String(64),nullable=False),
            sa.Column("customer_name",sa.String(100),nullable=False),
            sa.Column("phone",sa.String(30),nullable=False),
            sa.Column("address",sa.String(300),nullable=False),
            sa.Column("note",sa.String(180),nullable=False),
            sa.Column("lines",sa.JSON(),nullable=False),
            sa.Column("total_vnd",sa.BigInteger(),nullable=False),
            sa.Column("status",sa.String(20),nullable=False),
            sa.Column("sale_order_id",sa.String(36),sa.ForeignKey("sale_orders.id")),
            sa.Column("review_reason",sa.String(180),nullable=False),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint("business_id","request_hash",name="uq_public_order_tenant_request"),
        )
    indexes={x["name"] for x in inspect(bind).get_indexes("public_order_requests")}
    if "ix_public_order_requests_business_id" not in indexes:
        op.create_index("ix_public_order_requests_business_id",
                        "public_order_requests",["business_id"])
    if "ix_public_orders_business_status" not in indexes:
        op.create_index("ix_public_orders_business_status",
                        "public_order_requests",["business_id","status","created_at"])

def downgrade():
    raise RuntimeError("No automatic destructive downgrade")
