"""One actual image per merchant product, tenant-scoped and bounded."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261116_09"
down_revision = "20261116_08"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not inspect(bind).has_table("product_media"):
        op.create_table(
            "product_media",
            sa.Column("product_id", sa.String(36),
                      sa.ForeignKey("products.id", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("content_type", sa.String(40),
                      nullable=False, server_default="image/webp"),
            sa.Column("revision", sa.String(32), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
    if "ix_product_media_business_id" not in {
        ix["name"] for ix in inspect(bind).get_indexes("product_media")
    }:
        op.create_index("ix_product_media_business_id", "product_media",
                        ["business_id"])


def downgrade():
    raise RuntimeError("Product photographs are business data and must not be removed silently")
