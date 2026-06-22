"""add media_analysis to chk_agent_name constraint

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-22
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_tasks DROP CONSTRAINT IF EXISTS chk_agent_name")
    op.execute("""
        ALTER TABLE agent_tasks ADD CONSTRAINT chk_agent_name CHECK (
            agent_name IN (
                'orchestrator', 'search_rag', 'reviewer',
                'editor', 'signature', 'translator', 'media_analysis'
            )
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE agent_tasks DROP CONSTRAINT IF EXISTS chk_agent_name")
    op.execute("""
        ALTER TABLE agent_tasks ADD CONSTRAINT chk_agent_name CHECK (
            agent_name IN (
                'orchestrator', 'search_rag', 'reviewer',
                'editor', 'signature', 'translator'
            )
        )
    """)
