from sqlalchemy import (
    BIGINT,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

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
    Column("first_received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_received_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("completion_deadline", DateTime(timezone=True)),
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

trace_services = Table(
    "trace_services",
    metadata,
    Column("trace_id", LargeBinary(16), ForeignKey("traces.trace_id"), nullable=False),
    Column("service_id", BIGINT, ForeignKey("services.service_id"), nullable=False),
    PrimaryKeyConstraint("trace_id", "service_id"),
)
