"""Tenant-scoped brand uploads stored in PostgreSQL, not ephemeral Render disk."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "20261115_04"
down_revision = "20261114_03"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("storefront_media"):
        op.create_table(
            "storefront_media",
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("kind", sa.String(10), primary_key=True),
            sa.Column("content_type", sa.String(40), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("revision", sa.String(32), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    raise RuntimeError("Do not automatically delete uploaded business images")
