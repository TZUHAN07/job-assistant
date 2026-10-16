"""Persist per-version cover letter review results."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c10a14review"
down_revision = "e795885f8cb9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cover_letters", sa.Column("review_metadata", postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column("cover_letters", "review_metadata")
