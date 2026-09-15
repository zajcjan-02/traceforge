"""add retention index

Revision ID: 0007_retention
Revises: 0006_service_dependencies
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_retention"
down_revision = "0006_service_dependencies"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("traces", "last_received_at", nullable=True)
    op.create_index(
        "traces_retention_eligible",
        "traces",
        ["completeness_state", "last_received_at"],
        postgresql_where=sa.text("completeness_state IN ('COMPLETE', 'INCOMPLETE')"),
    )


def downgrade():
    op.drop_index("traces_retention_eligible", table_name="traces")
    op.alter_column("traces", "last_received_at", nullable=False)
