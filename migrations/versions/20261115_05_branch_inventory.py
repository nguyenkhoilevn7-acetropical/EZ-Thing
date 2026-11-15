"""Optional branch-location stock balances; never backfill automatically.

Activation requires explicit owner confirmation and a one-time physical stock
reconciliation. Until activated, Product.stock remains business-wide.
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "20261115_05"
down_revision = "20261115_04"
branch_labels = None
depends_on = None


def upgrade():
    bind=op.get_bind()
    if not inspect(bind).has_table("branch_stock_balances"):
        op.create_table(
            "branch_stock_balances",
            sa.Column("business_id",sa.String(36),
                      sa.ForeignKey("businesses.id",ondelete="CASCADE"),primary_key=True),
            sa.Column("branch_id",sa.String(36),
                      sa.ForeignKey("branches.id",ondelete="CASCADE"),primary_key=True),
            sa.Column("product_id",sa.String(36),
                      sa.ForeignKey("products.id",ondelete="CASCADE"),primary_key=True),
            sa.Column("quantity",sa.Integer(),nullable=False,server_default="0"),
            sa.CheckConstraint("quantity >= 0",name="ck_branch_stock_nonnegative")
        )


def downgrade():
    raise RuntimeError("Never automatically delete branch stock balances")
