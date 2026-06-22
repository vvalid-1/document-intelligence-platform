"""add folders table and folder_id to documents

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_folders_owner_id", "folders", ["owner_id"])
    op.create_unique_constraint("uq_folders_owner_name", "folders", ["owner_id", "name"])

    op.add_column(
        "documents",
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.drop_column("documents", "folder_id")
    op.drop_constraint("uq_folders_owner_name", "folders", type_="unique")
    op.drop_index("ix_folders_owner_id", table_name="folders")
    op.drop_table("folders")
