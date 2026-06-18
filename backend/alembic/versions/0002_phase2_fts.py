"""Phase 2 — document_chunks FTS search_vector + composite indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FTS search_vector on document_chunks (T-212)
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_fts ON document_chunks USING GIN(search_vector)"
    )

    # Composite indexes from DATABASE_SCHEMA.md not included in 0001
    op.execute(
        "CREATE INDEX idx_documents_list ON documents(owner_id, is_deleted, status, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_sessions_user_active ON agent_sessions(user_id, is_active, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_messages_session_seq ON agent_messages(session_id, sequence_num DESC)"
    )
    op.execute(
        "CREATE INDEX idx_tasks_session_created ON agent_tasks(session_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_audit_user_created ON audit_logs(user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_audit_created ON audit_logs(created_at DESC)"
    )


def downgrade() -> None:
    for idx in (
        "idx_audit_created",
        "idx_audit_user_created",
        "idx_tasks_session_created",
        "idx_messages_session_seq",
        "idx_sessions_user_active",
        "idx_documents_list",
        "ix_document_chunks_fts",
    ):
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector")
