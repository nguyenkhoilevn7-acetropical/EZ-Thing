"""Additive optional email-ownership verification schema for newly registered users."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision="20261114_02"
down_revision="20261114_01"
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    if not inspect(bind).has_table("auth_email_verifications"):
        op.create_table(
            "auth_email_verifications",
            sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),
            sa.Column("token_hash",sa.String(64),nullable=False),
            sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("verified_at",sa.DateTime(timezone=True)),
            sa.Column("sent_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("sends_count",sa.Integer(),nullable=False)
        )
    if not any(i["name"]=="ix_auth_email_verifications_token_hash"
               for i in inspect(bind).get_indexes("auth_email_verifications")):
        op.create_index("ix_auth_email_verifications_token_hash",
                        "auth_email_verifications",["token_hash"],unique=True)

def downgrade():
    raise RuntimeError("No destructive automatic downgrade")
