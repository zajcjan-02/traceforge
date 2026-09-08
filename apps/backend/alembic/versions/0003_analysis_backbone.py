"""add analysis jobs and runs

Revision ID: 0003_analysis_backbone
Revises: 0002_trace_lifecycle
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_analysis_backbone"
down_revision = "0002_trace_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_runs",
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", sa.LargeBinary(length=16), sa.ForeignKey("traces.trace_id"), nullable=False),
        sa.Column("trace_revision", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("analysis_version", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("job_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.LargeBinary(length=16), sa.ForeignKey("traces.trace_id"), nullable=False),
        sa.Column("trace_revision", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("trace_id", "trace_revision"),
    )
    op.add_column("traces", sa.Column("analysis_state", sa.Text()))
    op.add_column("traces", sa.Column("current_analysis_run_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "traces_current_analysis_run_id_fkey",
        "traces",
        "analysis_runs",
        ["current_analysis_run_id"],
        ["analysis_run_id"],
    )
    op.create_index(
        "analysis_jobs_pending",
        "analysis_jobs",
        ["available_at", "job_id"],
        postgresql_where=sa.text("state = 'PENDING'"),
    )
    op.create_index(
        "analysis_jobs_expired_lease",
        "analysis_jobs",
        ["lease_expires_at"],
        postgresql_where=sa.text("state = 'RUNNING'"),
    )


def downgrade():
    op.drop_index("analysis_jobs_expired_lease", table_name="analysis_jobs")
    op.drop_index("analysis_jobs_pending", table_name="analysis_jobs")
    op.drop_constraint("traces_current_analysis_run_id_fkey", "traces", type_="foreignkey")
    op.drop_column("traces", "current_analysis_run_id")
    op.drop_column("traces", "analysis_state")
    op.drop_table("analysis_jobs")
    op.drop_table("analysis_runs")
