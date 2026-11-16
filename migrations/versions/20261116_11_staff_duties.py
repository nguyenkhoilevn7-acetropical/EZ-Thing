"""Tenant staff station/task duty. A browser workstation profile is never authorization."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20261116_11"
down_revision="20261116_10"
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if not inspect(bind).has_table("staff_duties"):
        op.create_table(
            "staff_duties",
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("business_id",sa.String(36),
                      sa.ForeignKey("businesses.id",ondelete="CASCADE"),nullable=False),
            sa.Column("user_id",sa.String(36),
                      sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
            sa.Column("mode",sa.String(20),nullable=False,server_default="order"),
            sa.Column("branch_id",sa.String(36),
                      sa.ForeignKey("branches.id",ondelete="SET NULL"),nullable=True),
            sa.Column("station",sa.String(20),nullable=False,server_default="all"),
            sa.Column("updated_by",sa.String(36),
                      sa.ForeignKey("users.id"),nullable=False),
            sa.Column("updated_at",sa.DateTime(timezone=True),
                      nullable=False,server_default=sa.func.now()),
            sa.UniqueConstraint("business_id","user_id",name="uq_staff_duty_tenant_user"),
        )
    indexes={x["name"] for x in inspect(bind).get_indexes("staff_duties")}
    if "ix_staff_duties_business_id" not in indexes:
        op.create_index("ix_staff_duties_business_id","staff_duties",["business_id"])

def downgrade():
    raise RuntimeError("Do not silently delete employee task assignments and audit context")
