"""Create users without assigning legacy MVP data.

Revision ID: e30authusers
Revises: d26a10interview
"""
from alembic import op
import sqlalchemy as sa

revision = "e30authusers"
down_revision = "d26a10interview"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(start=2), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email"),
    )


def downgrade():
    op.drop_table("users")
