"""Extraction, rules, drafts, retry state, and single-use OAuth state."""
import sqlalchemy as sa
from alembic import op
revision = "0002"
down_revision = "0001"


def upgrade():
    for column in (
        sa.Column("headers", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("entities", sa.JSON, nullable=True),
        sa.Column("action_plan", sa.JSON, nullable=True),
        sa.Column("actions_applied", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("messages", column)
    op.create_table("rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("definition", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("drafts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_id", sa.Integer, sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("gmail_draft_id", sa.String(128)),
        sa.Column("gmail_message_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("oauth_states",
        sa.Column("nonce", sa.String(128), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("oauth_states")
    op.drop_table("drafts")
    op.drop_table("rules")
    with op.batch_alter_table("messages") as batch:
        for name in ("headers", "entities", "action_plan", "actions_applied", "attempts", "next_attempt_at"):
            batch.drop_column(name)
