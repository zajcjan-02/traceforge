"""add repeated database finding tables

Revision ID: 0004_repeated_database_findings
Revises: 0003_analysis_backbone
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_repeated_database_findings"
down_revision = "0003_analysis_backbone"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "detector_results",
        sa.Column("detector_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.analysis_run_id"), nullable=False),
        sa.Column("detector_id", sa.Text(), nullable=False),
        sa.Column("detector_version", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("duration_ns", sa.BigInteger()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", "detector_id", "detector_version"),
    )
    op.create_table(
        "findings",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.analysis_run_id"), nullable=False),
        sa.Column("trace_id", sa.LargeBinary(length=16), sa.ForeignKey("traces.trace_id"), nullable=False),
        sa.Column("trace_revision", sa.BigInteger(), nullable=False),
        sa.Column("detector_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("detector_results.detector_result_id"), nullable=False),
        sa.Column("finding_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("interpretation", sa.Text()),
        sa.Column("structured_data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "finding_evidence",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.finding_id"), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("structured_data", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text()),
    )
    op.create_table(
        "finding_spans",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.finding_id"), nullable=False),
        sa.Column("trace_id", sa.LargeBinary(length=16), nullable=False),
        sa.Column("span_id", sa.LargeBinary(length=8), nullable=False),
        sa.Column("relation", sa.Text()),
        sa.PrimaryKeyConstraint("finding_id", "trace_id", "span_id"),
        sa.ForeignKeyConstraint(["trace_id", "span_id"], ["spans.trace_id", "spans.span_id"]),
    )


def downgrade():
    op.drop_table("finding_spans")
    op.drop_table("finding_evidence")
    op.drop_table("findings")
    op.drop_table("detector_results")
