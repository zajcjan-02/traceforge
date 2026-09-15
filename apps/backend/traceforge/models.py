from sqlalchemy import (
    BIGINT,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

traces = Table(
    "traces",
    metadata,
    Column("trace_id", LargeBinary(16), primary_key=True),
    Column("revision", BIGINT, nullable=False),
    Column("first_span_start_ns", BIGINT, nullable=False),
    Column("last_span_end_ns", BIGINT),
    Column("duration_ns", BIGINT),
    Column("span_count", Integer, nullable=False),
    Column("completeness_state", String, nullable=False),
    Column("analysis_state", String),
    Column("current_analysis_run_id", UUID(as_uuid=True)),
    Column("first_received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_received_at", DateTime(timezone=True), server_default=func.now()),
    Column("completion_deadline", DateTime(timezone=True)),
)

analysis_jobs = Table(
    "analysis_jobs",
    metadata,
    Column("job_id", BIGINT, primary_key=True, autoincrement=True),
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("trace_revision", BIGINT, nullable=False),
    Column("state", String, nullable=False),
    Column("attempt_count", Integer, nullable=False, server_default="0"),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("claimed_at", DateTime(timezone=True)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("claim_token", UUID(as_uuid=True)),
    Column("completed_at", DateTime(timezone=True)),
    Column("last_error", String),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("trace_id", "trace_revision"),
)

analysis_runs = Table(
    "analysis_runs",
    metadata,
    Column("analysis_run_id", UUID(as_uuid=True), primary_key=True),
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("trace_revision", BIGINT, nullable=False),
    Column("state", String, nullable=False),
    Column("analysis_version", String, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("completed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

detector_results = Table(
    "detector_results",
    metadata,
    Column("detector_result_id", UUID(as_uuid=True), primary_key=True),
    Column("analysis_run_id", UUID(as_uuid=True), ForeignKey("analysis_runs.analysis_run_id"), nullable=False),
    Column("detector_id", String, nullable=False),
    Column("detector_version", String, nullable=False),
    Column("state", String, nullable=False),
    Column("duration_ns", BIGINT),
    Column("failure_reason", String),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("analysis_run_id", "detector_id", "detector_version"),
)

findings = Table(
    "findings",
    metadata,
    Column("finding_id", UUID(as_uuid=True), primary_key=True),
    Column("analysis_run_id", UUID(as_uuid=True), ForeignKey("analysis_runs.analysis_run_id"), nullable=False),
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("trace_revision", BIGINT, nullable=False),
    Column("detector_result_id", UUID(as_uuid=True), ForeignKey("detector_results.detector_result_id"), nullable=False),
    Column("finding_type", String, nullable=False),
    Column("severity", String, nullable=False),
    Column("confidence", String, nullable=False),
    Column("title", String, nullable=False),
    Column("summary", String, nullable=False),
    Column("observation", String, nullable=False),
    Column("interpretation", String),
    Column("structured_data", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

finding_evidence = Table(
    "finding_evidence",
    metadata,
    Column("evidence_id", UUID(as_uuid=True), primary_key=True),
    Column("finding_id", UUID(as_uuid=True), ForeignKey("findings.finding_id"), nullable=False),
    Column("evidence_type", String, nullable=False),
    Column("structured_data", JSONB, nullable=False),
    Column("description", String),
)

finding_spans = Table(
    "finding_spans",
    metadata,
    Column("finding_id", UUID(as_uuid=True), ForeignKey("findings.finding_id"), nullable=False),
    Column("trace_id", LargeBinary(16), nullable=False),
    Column("span_id", LargeBinary(8), nullable=False),
    Column("relation", String),
    PrimaryKeyConstraint("finding_id", "trace_id", "span_id"),
    ForeignKeyConstraint(["trace_id", "span_id"], ["spans.trace_id", "spans.span_id"]),
)

services = Table(
    "services",
    metadata,
    Column("service_id", BIGINT, primary_key=True, autoincrement=True),
    Column("service_name", String, nullable=False),
    Column("namespace", String, nullable=False, server_default=""),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("service_name", "namespace"),
)

spans = Table(
    "spans",
    metadata,
    Column("trace_id", LargeBinary(16), nullable=False),
    Column("span_id", LargeBinary(8), nullable=False),
    Column("parent_span_id", LargeBinary(8)),
    Column("service_id", BIGINT, ForeignKey("services.service_id")),
    Column("name", String, nullable=False),
    Column("span_kind", String, nullable=False),
    Column("start_time_unix_ns", BIGINT, nullable=False),
    Column("end_time_unix_ns", BIGINT),
    Column("duration_ns", BIGINT),
    Column("status", String, nullable=False),
    Column("attributes", JSONB, nullable=False),
    Column("resource_attributes", JSONB, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("trace_id", "span_id"),
)

span_events = Table(
    "span_events",
    metadata,
    Column("event_id", BIGINT, primary_key=True, autoincrement=True),
    Column("trace_id", LargeBinary(16), nullable=False),
    Column("span_id", LargeBinary(8), nullable=False),
    Column("event_index", Integer, nullable=False),
    Column("name", String, nullable=False),
    Column("timestamp_unix_ns", BIGINT),
    Column("attributes", JSONB, nullable=False),
    ForeignKeyConstraint(["trace_id", "span_id"], ["spans.trace_id", "spans.span_id"]),
    UniqueConstraint("trace_id", "span_id", "event_index"),
)

trace_services = Table(
    "trace_services",
    metadata,
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("service_id", BIGINT, ForeignKey("services.service_id"), nullable=False),
    PrimaryKeyConstraint("trace_id", "service_id"),
)

service_dependency_observations = Table(
    "service_dependency_observations",
    metadata,
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("source_service_id", BIGINT, ForeignKey("services.service_id"), nullable=False),
    Column("target_service_id", BIGINT, ForeignKey("services.service_id"), nullable=False),
    Column("trace_revision", BIGINT, nullable=False),
    Column("observed_at", BIGINT, nullable=False),
    PrimaryKeyConstraint("trace_id", "source_service_id", "target_service_id"),
)
