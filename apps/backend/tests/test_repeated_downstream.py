from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import detector_results, finding_evidence, finding_spans, findings, traces
from traceforge.repeated_downstream import detect
from traceforge.worker import claim_job, complete_job

client = TestClient(app)


def span(span_id, attributes=None, service_id=1, service_name="orders", start=0, end=10):
    return {
        "span_id": span_id.to_bytes(8, "big"),
        "service_id": service_id,
        "service_name": service_name,
        "span_kind": "CLIENT",
        "start_time_unix_ns": start,
        "end_time_unix_ns": end,
        "duration_ns": end - start,
        "attributes": attributes or {},
    }


def http_span(span_id, start=0, end=10, service_id=1, target="inventory", template="/products/{id}"):
    return span(
        span_id,
        {
            "http.request.method": "GET",
            "url.template": template,
            "server.address": target,
            "server.port": 8080,
        },
        service_id,
        "orders" if service_id == 1 else "checkout",
        start,
        end,
    )


def trace(state="COMPLETE"):
    return {"completeness_state": state}


def test_no_downstream_spans_is_not_applicable():
    assert detect(trace(), [span(1)])["state"] == "SKIPPED_NOT_APPLICABLE"


def test_ambiguous_http_identity_is_insufficient_data():
    result = detect(trace(), [span(1, {"http.request.method": "GET", "server.address": "inventory"})])

    assert result["state"] == "SKIPPED_INSUFFICIENT_DATA"


def test_http_groups_at_exact_threshold_with_structured_evidence():
    result = detect(trace(), [http_span(index, index * 20, index * 20 + 10) for index in range(5)])

    finding = result["findings"][0]
    assert result["state"] == "SUCCESS_WITH_FINDINGS"
    assert finding["type"] == "REPEATED_DOWNSTREAM_OPERATION"
    assert finding["severity"] == "MEDIUM"
    assert finding["confidence"] == "HIGH"
    assert finding["structured_data"] == {
        "count": 5,
        "sequential_count": 5,
        "combined_duration_ns": 50,
        "normalized_operation": "GET /products/{id}",
        "source_service": "orders",
        "target_peer": "inventory:8080",
        "protocol": "HTTP",
    }
    assert [item["type"] for item in finding["evidence"]] == [
        "DOWNSTREAM_OPERATION_COUNT",
        "DOWNSTREAM_OPERATION_TIMING",
        "DOWNSTREAM_OPERATION_CONTEXT",
    ]


def test_below_threshold_and_different_services_targets_and_paths_do_not_merge():
    spans = [http_span(index) for index in range(4)]
    spans += [http_span(index + 4, service_id=2) for index in range(4)]
    spans += [http_span(index + 8, target="payments") for index in range(4)]
    spans += [http_span(index + 12, template="/categories/{id}") for index in range(4)]

    assert detect(trace(), spans)["state"] == "SUCCESS_NO_FINDINGS"


def test_rpc_groups_by_system_method_and_target():
    attributes = {
        "rpc.system.name": "grpc",
        "rpc.method": "/inventory.Inventory/GetProduct",
        "server.address": "inventory",
    }
    result = detect(trace(), [span(index, attributes, start=index * 20, end=index * 20 + 10) for index in range(5)])

    finding = result["findings"][0]
    assert finding["structured_data"]["protocol"] == "RPC:grpc"
    assert finding["structured_data"]["normalized_operation"] == "/inventory.Inventory/GetProduct"
    assert finding["structured_data"]["target_peer"] == "inventory"


def test_concurrent_calls_are_low_severity_and_related_spans_are_stable():
    result = detect(trace("INCOMPLETE"), [http_span(index, index, 100) for index in range(5)])

    finding = result["findings"][0]
    assert finding["severity"] == "LOW"
    assert finding["confidence"] == "MEDIUM"
    assert finding["structured_data"]["sequential_count"] == 1
    assert [span["span_id"] for span in finding["spans"]] == [index.to_bytes(8, "big") for index in range(5)]


def request(trace_id):
    export = ExportTraceServiceRequest()
    resource = export.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "orders"
    scope = export.resource_spans[0].scope_spans.add()
    root = scope.spans.add()
    root.trace_id = bytes.fromhex(trace_id)
    root.span_id = (1).to_bytes(8, "big")
    root.name = "request"
    root.kind = Span.SPAN_KIND_SERVER
    root.start_time_unix_nano = 0
    root.end_time_unix_nano = 200
    for index in range(5):
        downstream = scope.spans.add()
        downstream.trace_id = root.trace_id
        downstream.span_id = (index + 2).to_bytes(8, "big")
        downstream.parent_span_id = root.span_id
        downstream.name = "inventory request"
        downstream.kind = Span.SPAN_KIND_CLIENT
        downstream.start_time_unix_nano = index * 20
        downstream.end_time_unix_nano = index * 20 + 10
        downstream.attributes.add(key="http.request.method").value.string_value = "GET"
        downstream.attributes.add(key="url.template").value.string_value = "/products/{id}"
        downstream.attributes.add(key="server.address").value.string_value = "inventory"
    return export


def finalize(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    evaluate_expired_traces()


def test_worker_persists_current_finding_evidence_and_span_references():
    trace_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/v1/traces",
        content=request(trace_id).SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    finalize(trace_id)
    assert complete_job(claim_job())

    with engine.connect() as connection:
        result = connection.execute(
            select(detector_results).where(detector_results.c.detector_id == "repeated_downstream_operation")
        ).mappings().one()
        finding = connection.execute(select(findings).where(findings.c.finding_type == "REPEATED_DOWNSTREAM_OPERATION")).mappings().one()
        assert connection.execute(select(func.count()).select_from(finding_evidence)).scalar_one() == 3
        assert connection.execute(select(func.count()).select_from(finding_spans)).scalar_one() == 5

    detail = client.get(f"/api/v1/traces/{trace_id}").json()
    current = next(item for item in detail["analysis"]["current_run"]["findings"] if item["type"] == "REPEATED_DOWNSTREAM_OPERATION")
    assert result["state"] == "SUCCESS_WITH_FINDINGS"
    assert finding["structured_data"]["count"] == 5
    assert len(current["related_span_ids"]) == 5
    assert "retry" not in current["summary"].lower()
    assert "retry" not in current["interpretation"].lower()


def test_stale_downstream_run_is_not_published_as_current():
    trace_id = "0123456789abcdef0123456789abcdef"
    client.post("/v1/traces", content=request(trace_id).SerializeToString(), headers={"content-type": "application/x-protobuf"})
    finalize(trace_id)
    job = claim_job()

    export = request(trace_id)
    late = export.resource_spans[0].scope_spans[0].spans.add()
    late.trace_id = bytes.fromhex(trace_id)
    late.span_id = (9).to_bytes(8, "big")
    late.parent_span_id = (1).to_bytes(8, "big")
    late.name = "late"
    late.kind = Span.SPAN_KIND_INTERNAL
    late.start_time_unix_nano = 210
    late.end_time_unix_nano = 220
    client.post("/v1/traces", content=export.SerializeToString(), headers={"content-type": "application/x-protobuf"})

    assert complete_job(job)
    assert client.get(f"/api/v1/traces/{trace_id}").json()["analysis"]["current_run"] is None
