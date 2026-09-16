from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import traces

client = TestClient(app)


def request_with_span(trace_id, span_id, parent_span_id=None, end_time=250):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "orders"
    scope = request.resource_spans[0].scope_spans.add()
    span = scope.spans.add()
    span.trace_id = bytes.fromhex(trace_id)
    span.span_id = bytes.fromhex(span_id)
    if parent_span_id is not None:
        span.parent_span_id = bytes.fromhex(parent_span_id)
    span.name = "operation"
    span.kind = Span.SPAN_KIND_INTERNAL
    span.start_time_unix_nano = 100
    if end_time is not None:
        span.end_time_unix_nano = end_time
    return request


def send(request):
    return client.post(
        "/v1/traces",
        content=request.SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )


def trace(trace_id):
    with engine.connect() as connection:
        return connection.execute(
            select(traces).where(traces.c.trace_id == bytes.fromhex(trace_id))
        ).mappings().one()


def expire(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=func.now() - timedelta(seconds=1))
        )


def test_trace_remains_processing_before_its_deadline():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "PROCESSING"


def test_normal_trace_becomes_complete_after_quiet_period():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    expire(trace_id)

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "COMPLETE"


def test_missing_parent_becomes_incomplete():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef", "fedcba9876543210"))
    expire(trace_id)

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "INCOMPLETE"


def test_child_before_parent_becomes_complete_when_parent_arrives():
    trace_id = "0123456789abcdef0123456789abcdef"
    parent_id = "fedcba9876543210"
    send(request_with_span(trace_id, "0123456789abcdef", parent_id))
    send(request_with_span(trace_id, parent_id))
    expire(trace_id)

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "COMPLETE"


def test_multiple_roots_become_incomplete():
    trace_id = "0123456789abcdef0123456789abcdef"
    request = request_with_span(trace_id, "0123456789abcdef")
    scope = request.resource_spans[0].scope_spans[0]
    second_span = scope.spans.add()
    second_span.trace_id = bytes.fromhex(trace_id)
    second_span.span_id = bytes.fromhex("fedcba9876543210")
    second_span.name = "second root"
    second_span.kind = Span.SPAN_KIND_INTERNAL
    second_span.start_time_unix_nano = 100
    second_span.end_time_unix_nano = 250
    send(request)
    expire(trace_id)

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "INCOMPLETE"


def test_missing_end_time_becomes_incomplete():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef", end_time=None))
    expire(trace_id)

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "INCOMPLETE"


def test_late_span_reopens_complete_trace_and_resets_deadline():
    trace_id = "0123456789abcdef0123456789abcdef"
    first_span_id = "0123456789abcdef"
    send(request_with_span(trace_id, first_span_id))
    expire(trace_id)
    evaluate_expired_traces()

    send(request_with_span(trace_id, "fedcba9876543210", first_span_id))

    reopened = trace(trace_id)
    assert reopened["completeness_state"] == "PROCESSING"
    assert reopened["revision"] == 2
    assert reopened["completion_deadline"] > datetime.now(timezone.utc)


def test_late_span_replaces_the_previous_deadline():
    trace_id = "0123456789abcdef0123456789abcdef"
    first_span_id = "0123456789abcdef"
    send(request_with_span(trace_id, first_span_id))
    first_deadline = trace(trace_id)["completion_deadline"]
    expire(trace_id)
    evaluate_expired_traces()

    send(request_with_span(trace_id, "fedcba9876543210", first_span_id))

    assert trace(trace_id)["completion_deadline"] > first_deadline


def test_expired_deadline_is_evaluated_after_database_reconnect():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    expire(trace_id)
    engine.dispose()

    evaluate_expired_traces()

    assert trace(trace_id)["completeness_state"] == "COMPLETE"
