"""add is_archived and archived_at to documents

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("documents", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_is_archived", "documents", ["is_archived"])


def downgrade() -> None:
    op.drop_index("ix_documents_is_archived", table_name="documents")
    op.drop_column("documents", "archived_at")
    op.drop_column("documents", "is_archived")
