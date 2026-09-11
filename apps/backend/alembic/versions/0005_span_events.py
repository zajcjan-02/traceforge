"""add span events

Revision ID: 0005_span_events
Revises: 0004_repeated_database_findings
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_span_events"
down_revision = "0004_repeated_database_findings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "span_events",
        sa.Column("event_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.LargeBinary(length=16), nullable=False),
        sa.Column("span_id", sa.LargeBinary(length=8), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timestamp_unix_ns", sa.BigInteger()),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["trace_id", "span_id"], ["spans.trace_id", "spans.span_id"]),
        sa.UniqueConstraint("trace_id", "span_id", "event_index"),
    )


def downgrade():
    op.drop_table("span_events")
