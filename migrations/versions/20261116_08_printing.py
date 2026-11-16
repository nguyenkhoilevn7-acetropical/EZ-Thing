"""EZ Print additive schema: device registration and immutable print jobs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261116_08"
down_revision = "20261115_07"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("print_devices"):
        op.create_table(
            "print_devices",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("protocol", sa.String(20), nullable=False),
            sa.Column("station", sa.String(12), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("auto_print", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        )
    ix = {x["name"] for x in inspect(bind).get_indexes("print_devices")}
    if "ix_print_devices_business_branch" not in ix:
        op.create_index("ix_print_devices_business_branch", "print_devices", ["business_id", "branch_id"])
    if not inspect(bind).has_table("print_jobs"):
        op.create_table(
            "print_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("device_id", sa.String(36), sa.ForeignKey("print_devices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_key", sa.String(140), nullable=False),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("last_error", sa.String(240), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("delivered_at", sa.DateTime(timezone=True)),
            sa.Column("printed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("device_id", "event_key", name="uq_print_device_event"),
        )
    ix = {x["name"] for x in inspect(bind).get_indexes("print_jobs")}
    if "ix_print_jobs_claim" not in ix:
        op.create_index("ix_print_jobs_claim", "print_jobs", ["device_id", "status", "created_at"])
    if "ix_print_jobs_tenant_created" not in ix:
        op.create_index("ix_print_jobs_tenant_created", "print_jobs", ["business_id", "created_at"])


def downgrade():
    raise RuntimeError("Printer devices and their print audit history must not be silently deleted")
