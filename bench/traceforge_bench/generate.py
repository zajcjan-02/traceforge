import hashlib
from dataclasses import dataclass

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span


PROFILES = {
    "small": {"trace_count": 1_000, "spans_per_trace": 10, "service_count": 4, "concurrency": 4, "batch_size": 25, "target_rate": 1_000},
    "medium": {"trace_count": 10_000, "spans_per_trace": 15, "service_count": 4, "concurrency": 8, "batch_size": 50, "target_rate": 1_000},
    "large": {"trace_count": 100_000, "spans_per_trace": 10, "service_count": 4, "concurrency": 16, "batch_size": 100, "target_rate": 5_000},
    "retention": {"trace_count": 20, "spans_per_trace": 10, "service_count": 4, "concurrency": 2, "batch_size": 10, "target_rate": None},
}


@dataclass(frozen=True)
class Workload:
    run_id: str
    trace_count: int
    spans_per_trace: int
    service_count: int
    batch_size: int
    concurrency: int
    target_rate: int | None
    pattern: str
    base_time_ns: int

    @property
    def prefix(self):
        return hashlib.sha256(self.run_id.encode()).digest()[:8]

    @property
    def expected_spans(self):
        return self.trace_count * self.spans_per_trace


def trace_id(workload, index):
    return workload.prefix + index.to_bytes(8, "big")


def span_id(index):
    return index.to_bytes(8, "big")


def request_for_traces(workload, indexes):
    request = ExportTraceServiceRequest()
    resources = {}
    for index in indexes:
        trace = trace_id(workload, index)
        start = workload.base_time_ns + index * 1_000_000
        root_id = span_id(1)
        by_service = {}
        for position in range(workload.spans_per_trace):
            database_operation = workload.pattern == "mixed-findings" and index % 10 == 0 and 1 <= position <= 5
            service = 0 if database_operation else position % workload.service_count
            by_service.setdefault(service, []).append(position)
        for service, positions in by_service.items():
            resource = resources.get(service)
            if resource is None:
                resource = request.resource_spans.add()
                resource.resource.attributes.add(
                    key="service.name"
                ).value.string_value = f"benchmark-service-{service}"
                resources[service] = resource
            scope = resource.scope_spans.add()
            for position in positions:
                database_operation = workload.pattern == "mixed-findings" and index % 10 == 0 and 1 <= position <= 5
                span = scope.spans.add()
                span.trace_id = trace
                span.span_id = root_id if position == 0 else span_id(position + 1)
                span.name = "benchmark request" if position == 0 else "benchmark work"
                span.kind = Span.SPAN_KIND_SERVER if position == 0 else Span.SPAN_KIND_INTERNAL
                span.start_time_unix_nano = start if position == 0 else start + position * 100_000
                span.end_time_unix_nano = start + workload.spans_per_trace * 100_000 if position == 0 else start + position * 100_000 + 50_000
                if position:
                    span.parent_span_id = root_id
                if database_operation:
                    span.name = "SELECT product"
                    span.kind = Span.SPAN_KIND_CLIENT
                    span.attributes.add(key="db.system.name").value.string_value = "postgresql"
                    span.attributes.add(key="db.query.text").value.string_value = f"SELECT name FROM product WHERE id = {position}"
    return request


def batches(workload):
    for first in range(0, workload.trace_count, workload.batch_size):
        indexes = list(range(first, min(first + workload.batch_size, workload.trace_count)))
        yield indexes, request_for_traces(workload, indexes).SerializeToString()


def manifest(workload):
    return {
        "run_id": workload.run_id,
        "trace_prefix_hex": workload.prefix.hex(),
        "trace_count": workload.trace_count,
        "spans_per_trace": workload.spans_per_trace,
        "expected_spans": workload.expected_spans,
        "service_count": workload.service_count,
        "batch_size": workload.batch_size,
        "concurrency": workload.concurrency,
        "target_rate": workload.target_rate,
        "pattern": workload.pattern,
        "base_time_ns": workload.base_time_ns,
        "trace_lower_hex": trace_id(workload, 0).hex(),
        "trace_upper_hex": trace_id(workload, workload.trace_count).hex(),
    }
