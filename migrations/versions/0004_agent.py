"""Knowledge, preferences, bounded agent runs and draft verification."""
import sqlalchemy as sa
from alembic import op
revision = "0004"
down_revision = "0003"


def upgrade():
    op.create_table("knowledge_documents", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("agent_preferences", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("instructions", sa.Text(), nullable=False))
    op.create_table("agent_runs", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False), sa.Column("input_chars", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_agent_runs_message_id", "agent_runs", ["message_id"])
    with op.batch_alter_table("drafts") as batch:
        batch.add_column(sa.Column("sources", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("verification", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("agent_run_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_drafts_agent_run", "agent_runs", ["agent_run_id"], ["id"], ondelete="SET NULL")
    with op.batch_alter_table("drafts") as batch:
        batch.alter_column("sources", server_default=None)
        batch.alter_column("verification", server_default=None)


def downgrade():
    with op.batch_alter_table("drafts") as batch:
        batch.drop_constraint("fk_drafts_agent_run", type_="foreignkey")
        batch.drop_column("agent_run_id")
        batch.drop_column("verification")
        batch.drop_column("sources")
    op.drop_table("agent_runs")
    op.drop_table("agent_preferences")
    op.drop_table("knowledge_documents")
