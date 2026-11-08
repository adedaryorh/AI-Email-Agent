"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "mailboxes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=False),
        sa.Column("history_id", sa.String(64)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "mailbox_id",
            sa.Integer,
            sa.ForeignKey("mailboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gmail_id", sa.String(64), nullable=False),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("sender", sa.String(512), nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column("has_unsubscribe", sa.Boolean, nullable=False),
        sa.Column("label_ids", sa.JSON, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mailbox_id", "gmail_id", name="uq_message_mailbox_gmail"),
    )
    op.create_index("ix_messages_mailbox_id", "messages", ["mailbox_id"])
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_messages_status", "messages", ["status"])
    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer,
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_classifications_message_id", "classifications", ["message_id"])
    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer,
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("detail", sa.JSON, nullable=False),
        sa.Column("actor", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_action_logs_message_id", "action_logs", ["message_id"])


def downgrade() -> None:
    for table in ("action_logs", "classifications", "messages", "mailboxes"):
        op.drop_table(table)
