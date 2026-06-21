"""add translator to chk_agent_name constraint

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-21
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_tasks DROP CONSTRAINT chk_agent_name")
    op.execute(
        "ALTER TABLE agent_tasks ADD CONSTRAINT chk_agent_name "
        "CHECK (agent_name IN ('orchestrator','search_rag','reviewer','editor','signature','translator'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_tasks DROP CONSTRAINT chk_agent_name")
    op.execute(
        "ALTER TABLE agent_tasks ADD CONSTRAINT chk_agent_name "
        "CHECK (agent_name IN ('orchestrator','search_rag','reviewer','editor','signature'))"
    )
