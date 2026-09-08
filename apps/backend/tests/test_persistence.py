from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status
from sqlalchemy import func, select

from traceforge.database import engine
from traceforge.main import app
from traceforge.models import services, spans, trace_services, traces

client = TestClient(app)


def export_request(trace_id="0123456789abcdef0123456789abcdef", span_id="0123456789abcdef"):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "orders"
    scope = request.resource_spans[0].scope_spans.add()
    span = scope.spans.add()
    span.trace_id = bytes.fromhex(trace_id)
    span.span_id = bytes.fromhex(span_id)
    span.name = "GET /orders"
    span.kind = Span.SPAN_KIND_SERVER
    span.start_time_unix_nano = 100
    span.end_time_unix_nano = 250
    span.status.code = Status.STATUS_CODE_OK
    span.attributes.add(key="http.response.status_code").value.int_value = 200
    return request


def send(request):
    return client.post(
        "/v1/traces",
        content=request.SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )


def test_persists_normalized_span():
    response = send(export_request())

    assert response.status_code == 200
    with engine.connect() as connection:
        span = connection.execute(select(spans)).mappings().one()

    assert span["trace_id"].hex() == "0123456789abcdef0123456789abcdef"
    assert span["parent_span_id"] is None
    assert span["duration_ns"] == 150
    assert span["attributes"] == {"http.response.status_code": 200}
    assert span["resource_attributes"] == {"service.name": "orders"}


def test_duplicate_ingestion_is_ignored():
    request = export_request()
    send(request)
    send(request)

    with engine.connect() as connection:
        trace = connection.execute(select(traces)).mappings().one()
        span_count = connection.execute(select(func.count()).select_from(spans)).scalar_one()

    assert span_count == 1
    assert trace["span_count"] == 1
    assert trace["revision"] == 1


def test_discovers_service_without_namespace_duplicates():
    send(export_request())
    send(export_request(trace_id="fedcba9876543210fedcba9876543210"))

    with engine.connect() as connection:
        service = connection.execute(select(services)).mappings().one()
        memberships = connection.execute(select(func.count()).select_from(trace_services)).scalar_one()

    assert service["service_name"] == "orders"
    assert service["namespace"] == ""
    assert memberships == 2


def test_lists_and_retrieves_trace():
    send(export_request())

    traces_response = client.get("/api/v1/traces")
    detail_response = client.get("/api/v1/traces/0123456789abcdef0123456789abcdef")

    assert traces_response.status_code == 200
    assert traces_response.json()["items"][0]["span_count"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["spans"][0]["duration_ns"] == 150
    assert detail_response.json()["spans"][0]["service"]["name"] == "orders"
    assert detail_response.json()["trace"]["completeness_state"] == "PROCESSING"


def test_returns_404_for_unknown_trace():
    response = client.get("/api/v1/traces/0123456789abcdef0123456789abcdef")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRACE_NOT_FOUND"
