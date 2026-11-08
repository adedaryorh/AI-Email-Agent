"""Revocable browser sessions."""
import sqlalchemy as sa
from alembic import op
revision = "0003"
down_revision = "0002"

def upgrade():
    op.create_table("web_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("credential_version", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_web_sessions_expires_at", "web_sessions", ["expires_at"])

def downgrade():
    op.drop_table("web_sessions")
