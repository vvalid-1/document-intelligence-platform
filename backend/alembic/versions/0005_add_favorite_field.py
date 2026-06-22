"""add is_favorite to documents

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_documents_is_favorite", "documents", ["is_favorite"])


def downgrade() -> None:
    op.drop_index("ix_documents_is_favorite", table_name="documents")
    op.drop_column("documents", "is_favorite")
