"""Additive team invitation and real storefront publication schema.

The migration is safe to re-run when pilot create_all has already provisioned
these tables. Existing data is untouched; drops are intentionally disabled.
"""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "20261114_01"
down_revision = "20261114_00"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    if not inspector.has_table("team_invitations"):
        op.create_table(
            "team_invitations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True)),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    inspector = inspect(connection)
    if not any(i["name"] == "ix_team_invitations_business_id" for i in
               inspector.get_indexes("team_invitations")):
        op.create_index("ix_team_invitations_business_id", "team_invitations", ["business_id"])
    if not inspector.has_table("public_storefronts"):
        op.create_table(
            "public_storefronts",
            sa.Column("business_id", sa.String(36),
                      sa.ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("slug", sa.String(60), nullable=False, unique=True),
            sa.Column("published", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    inspector = inspect(connection)
    if not any(i["name"] == "ix_public_storefronts_slug" for i in
               inspector.get_indexes("public_storefronts")):
        op.create_index("ix_public_storefronts_slug", "public_storefronts", ["slug"])

def downgrade():
    raise RuntimeError("Automatic destructive schema rollback is disabled")
