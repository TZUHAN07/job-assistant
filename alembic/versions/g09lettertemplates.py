"""Add immutable, resume-bound cover letter templates."""
from alembic import op
import sqlalchemy as sa
revision = "g09lettertemplates"
down_revision = "f30authsessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("cover_letter_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("resume_hash", sa.String(64), nullable=False),
        sa.Column("opening", sa.Text(), nullable=False),
        sa.Column("why_me", sa.Text(), nullable=False),
        sa.Column("call_to_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_cover_letter_templates_user_id", "cover_letter_templates", ["user_id"])
    op.create_index("ix_cover_letter_templates_resume_id", "cover_letter_templates", ["resume_id"])


def downgrade():
    op.drop_table("cover_letter_templates")
