"""Create interview sets with evidence snapshots.

Revision ID: d26a10interview
Revises: c10a14review
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d26a10interview"
down_revision = "c10a14review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("matching_id", sa.Integer(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["matching_id"], ["matchings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_sets_user_id", "interview_sets", ["user_id"])
    op.create_index("ix_interview_sets_matching_id", "interview_sets", ["matching_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_sets_matching_id", table_name="interview_sets")
    op.drop_index("ix_interview_sets_user_id", table_name="interview_sets")
    op.drop_table("interview_sets")
