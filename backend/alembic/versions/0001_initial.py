"""Initial schema — all tables, triggers, indexes

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('admin', 'editor', 'viewer')", name="chk_user_role"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    # ── user_invitations ───────────────────────────────────────────────────────
    op.create_table(
        "user_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("token_hash", name="uq_inv_token"),
        sa.CheckConstraint("role IN ('admin', 'editor', 'viewer')", name="chk_inv_role"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], name="fk_inv_invited_by", ondelete="CASCADE"),
    )
    op.create_index("ix_user_invitations_email", "user_invitations", ["email"])
    op.create_index("ix_user_invitations_token_hash", "user_invitations", ["token_hash"])

    # ── refresh_tokens ─────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_refresh_user", ondelete="CASCADE"),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # ── sse_tokens ─────────────────────────────────────────────────────────────
    op.create_table(
        "sse_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("token_hash", name="uq_sse_token_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sse_user", ondelete="CASCADE"),
    )
    op.create_index("ix_sse_tokens_token_hash", "sse_tokens", ["token_hash"])

    # ── documents ──────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("doc_metadata", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("processing_step", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'error')",
            name="chk_doc_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_doc_owner", ondelete="SET NULL"),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_is_deleted", "documents", ["is_deleted"])

    # Full-text search vector — GENERATED ALWAYS AS STORED
    op.execute(
        """
        ALTER TABLE documents
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(title, '') || ' ' || coalesce(original_name, ''))
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_documents_search_vector ON documents USING GIN(search_vector)"
    )

    # ── document_chunks ────────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chroma_chunk_id", sa.String(255), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_idx"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_chunk_doc", ondelete="CASCADE"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_chroma_chunk_id", "document_chunks", ["chroma_chunk_id"])

    # ── agent_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_name", sa.String(255), nullable=True),
        sa.Column("context_summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_session_user", ondelete="CASCADE"),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index("ix_agent_sessions_is_active", "agent_sessions", ["is_active"])

    # ── agent_tasks ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("input_payload", postgresql.JSONB, nullable=False),
        sa.Column("output_payload", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("timed_out", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="chk_task_status",
        ),
        sa.CheckConstraint(
            "agent_name IN ('orchestrator', 'search_rag', 'reviewer', 'editor', 'signature')",
            name="chk_agent_name",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_task_session", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_task_doc", ondelete="SET NULL"),
    )
    op.create_index("ix_agent_tasks_session_id", "agent_tasks", ["session_id"])
    op.create_index("ix_agent_tasks_document_id", "agent_tasks", ["document_id"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])
    op.create_index("ix_agent_tasks_agent_name", "agent_tasks", ["agent_name"])

    # ── agent_messages ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence_num", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("session_id", "sequence_num", name="uq_messages_session_seq"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool', 'system')", name="chk_message_role"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name="fk_msg_session", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], name="fk_msg_task", ondelete="SET NULL"),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])
    op.create_index("ix_agent_messages_task_id", "agent_messages", ["task_id"])

    # ── document_versions ──────────────────────────────────────────────────────
    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("document_id", "version_number", name="uq_versions_doc_num"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_version_doc", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_version_creator", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], name="fk_version_task", ondelete="SET NULL"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_task_id", "document_versions", ["task_id"])

    # ── document_reviews ───────────────────────────────────────────────────────
    op.create_table(
        "document_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("issues", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 10)",
            name="chk_review_score",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_review_doc", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], name="fk_review_reviewer", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], name="fk_review_task", ondelete="SET NULL"),
    )
    op.create_index("ix_document_reviews_document_id", "document_reviews", ["document_id"])

    # ── signatures ─────────────────────────────────────────────────────────────
    op.create_table(
        "signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signature_type", sa.String(30), nullable=False),
        sa.Column("signature_image_path", sa.Text, nullable=True),
        sa.Column("field_name", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("position_data", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("signature_type IN ('typed', 'drawn')", name="chk_sig_type"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_sig_doc", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signed_by"], ["users.id"], name="fk_sig_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.id"], name="fk_sig_version", ondelete="SET NULL"),
    )
    op.create_index("ix_signatures_document_id", "signatures", ["document_id"])
    op.create_index("ix_signatures_signed_by", "signatures", ["signed_by"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])

    # ── Audit log immutability trigger ─────────────────────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only — UPDATE and DELETE are not allowed';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_immutable();
        """
    )

    # ── updated_at auto-update trigger for users ───────────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("users", "documents", "agent_sessions"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in ("users", "documents", "agent_sessions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_immutable")

    for tbl in [
        "audit_logs",
        "signatures",
        "document_reviews",
        "document_versions",
        "agent_messages",
        "agent_tasks",
        "agent_sessions",
        "document_chunks",
        "documents",
        "sse_tokens",
        "refresh_tokens",
        "user_invitations",
        "users",
    ]:
        op.drop_table(tbl)
