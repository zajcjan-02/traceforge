from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from traceforge.main import app

client = TestClient(app)


def test_live():
    response = client.get("/health/live")

    assert response.status_code == 200


def test_ready():
    response = client.get("/health/ready")

    assert response.status_code == 200


def test_ingests_valid_otlp_protobuf(caplog):
    request = ExportTraceServiceRequest()
    scope = request.resource_spans.add().scope_spans.add()
    scope.spans.add().name = "test-span"
    caplog.set_level("INFO")

    response = client.post(
        "/v1/traces",
        content=request.SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"
    assert response.content == b""
    assert "resource_spans=1 scope_spans=1 spans=1" in caplog.text


def test_rejects_malformed_protobuf():
    response = client.post(
        "/v1/traces",
        content=b"\x80",
        headers={"content-type": "application/x-protobuf"},
    )

    assert response.status_code == 400
