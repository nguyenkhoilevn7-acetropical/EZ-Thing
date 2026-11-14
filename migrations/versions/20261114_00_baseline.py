"""Version baseline for existing EZ Thing schema. Does not delete or create business rows.

Fresh installations must bootstrap baseline schema once with the reviewed pilot
bootstrap, then apply versioned upgrades. We do not silently stamp unknown DBs.
"""
from alembic import op
from sqlalchemy import inspect

revision = "20261114_00"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    inspector = inspect(op.get_bind())
    required = ("users", "businesses", "memberships", "products", "sale_orders",
                "sale_order_items", "stock_movements", "sessions")
    absent = [name for name in required if not inspector.has_table(name)]
    if absent:
        raise RuntimeError("Cannot baseline unknown/empty database, missing: " + ", ".join(absent))

def downgrade():
    raise RuntimeError("Baseline downgrade is disabled; use a verified snapshot restore")
