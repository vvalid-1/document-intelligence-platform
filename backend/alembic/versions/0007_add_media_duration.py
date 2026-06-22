"""add media_duration_seconds to documents

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("media_duration_seconds", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "media_duration_seconds")
