"""add service dependency observations

Revision ID: 0006_service_dependencies
Revises: 0005_span_events
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_service_dependencies"
down_revision = "0005_span_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_dependency_observations",
        sa.Column("trace_id", sa.LargeBinary(length=16), sa.ForeignKey("traces.trace_id"), nullable=False),
        sa.Column("source_service_id", sa.BigInteger(), sa.ForeignKey("services.service_id"), nullable=False),
        sa.Column("target_service_id", sa.BigInteger(), sa.ForeignKey("services.service_id"), nullable=False),
        sa.Column("trace_revision", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("trace_id", "source_service_id", "target_service_id"),
    )


def downgrade():
    op.drop_table("service_dependency_observations")
