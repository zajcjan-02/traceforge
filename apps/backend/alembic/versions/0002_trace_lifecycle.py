"""add trace lifecycle deadline

Revision ID: 0002_trace_lifecycle
Revises: 0001_persistence
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_trace_lifecycle"
down_revision = "0001_persistence"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("traces", sa.Column("completion_deadline", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE traces SET completion_deadline = NOW() + INTERVAL '2 seconds' "
        "WHERE completeness_state = 'PROCESSING'"
    )
    op.create_index(
        "traces_processing_deadline",
        "traces",
        ["completion_deadline"],
        postgresql_where=sa.text("completeness_state = 'PROCESSING'"),
    )


def downgrade():
    op.drop_index("traces_processing_deadline", table_name="traces")
    op.drop_column("traces", "completion_deadline")
