"""Persist assigned operating modes for POS terminals and kitchen screens."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261116_11"
down_revision = "20261116_10"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("workstations"):
        op.create_table(
            "workstations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("client_key", sa.String(36), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False,
                      server_default="manager"),
            sa.Column("station", sa.String(20), nullable=False,
                      server_default="all"),
            sa.Column("branch_id", sa.String(36),
                      sa.ForeignKey("branches.id", ondelete="SET NULL")),
            sa.Column("created_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_by", sa.String(36),
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("business_id", "client_key",
                                name="uq_workstation_business_key"),
        )
    indexes = {ix["name"] for ix in inspect(bind).get_indexes("workstations")}
    if "ix_workstations_business_id" not in indexes:
        op.create_index("ix_workstations_business_id", "workstations", ["business_id"])


def downgrade():
    raise RuntimeError("Device assignment records cannot be dropped without an explicit backup")
