"""create persistence tables

Revision ID: 0001_persistence
Revises:
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_persistence"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "traces",
        sa.Column("trace_id", sa.LargeBinary(length=16), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("first_span_start_ns", sa.BigInteger(), nullable=False),
        sa.Column("last_span_end_ns", sa.BigInteger()),
        sa.Column("duration_ns", sa.BigInteger()),
        sa.Column("span_count", sa.Integer(), nullable=False),
        sa.Column("completeness_state", sa.Text(), nullable=False),
        sa.Column("first_received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "services",
        sa.Column("service_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("service_name", sa.Text(), nullable=False),
        sa.Column("namespace", sa.Text(), server_default="", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("service_name", "namespace"),
    )
    op.create_table(
        "spans",
        sa.Column("trace_id", sa.LargeBinary(length=16), nullable=False),
        sa.Column("span_id", sa.LargeBinary(length=8), nullable=False),
        sa.Column("parent_span_id", sa.LargeBinary(length=8)),
        sa.Column("service_id", sa.BigInteger(), sa.ForeignKey("services.service_id")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("span_kind", sa.Text(), nullable=False),
        sa.Column("start_time_unix_ns", sa.BigInteger(), nullable=False),
        sa.Column("end_time_unix_ns", sa.BigInteger()),
        sa.Column("duration_ns", sa.BigInteger()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.Column("resource_attributes", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("trace_id", "span_id"),
    )
    op.create_table(
        "trace_services",
        sa.Column("trace_id", sa.LargeBinary(length=16), sa.ForeignKey("traces.trace_id"), nullable=False),
        sa.Column("service_id", sa.BigInteger(), sa.ForeignKey("services.service_id"), nullable=False),
        sa.PrimaryKeyConstraint("trace_id", "service_id"),
    )
    op.create_index("traces_last_received_at", "traces", ["last_received_at"])
    op.create_index("spans_trace_start", "spans", ["trace_id", "start_time_unix_ns"])
    op.create_index("trace_services_service", "trace_services", ["service_id", "trace_id"])


def downgrade():
    op.drop_index("trace_services_service", table_name="trace_services")
    op.drop_index("spans_trace_start", table_name="spans")
    op.drop_index("traces_last_received_at", table_name="traces")
    op.drop_table("trace_services")
    op.drop_table("spans")
    op.drop_table("services")
    op.drop_table("traces")
