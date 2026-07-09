"""Add message_type column to messages

Revision ID: 003_message_type
Revises: 002_multi_doc
Create Date: 2025-01-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_message_type"
down_revision: str | None = "002_multi_doc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("message_type", sa.String(), nullable=False, server_default="chat"),
    )


def downgrade() -> None:
    op.drop_column("messages", "message_type")
