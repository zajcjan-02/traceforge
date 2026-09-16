"""add trace search indexes

Revision ID: 0008_trace_search
Revises: 0007_retention
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_trace_search"
down_revision = "0007_retention"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("traces_start_time_trace", "traces", ["first_span_start_ns", "trace_id"])
    op.create_index(
        "spans_root_operation",
        "spans",
        ["name", "trace_id"],
        postgresql_where=sa.text("parent_span_id IS NULL"),
    )


def downgrade():
    op.drop_index("spans_root_operation", table_name="spans")
    op.drop_index("traces_start_time_trace", table_name="traces")
