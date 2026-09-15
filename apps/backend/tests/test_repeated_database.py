from datetime import timedelta

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import detector_results, finding_evidence, finding_spans, findings, spans, traces
from traceforge.repeated_database import detect
from traceforge.worker import claim_job, complete_job

client = TestClient(app)


def span(span_id, query=None, service_id=1, service_name="orders", start=0, end=10):
    attributes = {}
    if query is not None:
        attributes = {"db.system.name": "postgresql", "db.query.text": query}
    return {
        "span_id": bytes.fromhex(f"{span_id:016x}"),
        "service_id": service_id,
        "service_name": service_name,
        "start_time_unix_ns": start,
        "end_time_unix_ns": end,
        "duration_ns": end - start,
        "attributes": attributes,
    }


def trace(state="COMPLETE"):
    return {"completeness_state": state}


def test_no_database_spans_is_not_applicable():
    assert detect(trace(), [span(1)])["state"] == "SKIPPED_NOT_APPLICABLE"


def test_database_spans_below_threshold_have_no_findings():
    result = detect(trace(), [span(index, "SELECT name FROM product WHERE id = 12") for index in range(4)])

    assert result["state"] == "SUCCESS_NO_FINDINGS"


def test_equivalent_literal_values_produce_one_finding():
    queries = [
        "SELECT name FROM product WHERE id = 12",
        "SELECT name FROM product WHERE id = 83",
        "SELECT name FROM product WHERE id = 'alice'",
        "SELECT name FROM product WHERE id = 'bob'",
        "SELECT name FROM product WHERE id = '25cb8d3c-1234-5678-9abc-def012345678'",
    ]
    result = detect(trace(), [span(index, query, start=index * 20, end=index * 20 + 10) for index, query in enumerate(queries)])

    assert result["state"] == "SUCCESS_WITH_FINDINGS"
    assert result["findings"][0]["structured_data"]["count"] == 5
    assert result["findings"][0]["structured_data"]["normalized_operation"] == "SELECT name FROM product WHERE id = ?"


def test_different_sql_and_services_do_not_merge():
    different_sql = [span(index, "SELECT name FROM product WHERE id = 12") for index in range(3)]
    different_sql += [span(index + 3, "SELECT name FROM category WHERE id = 12") for index in range(2)]
    different_services = [span(index, "SELECT name FROM product WHERE id = 12", service_id=2) for index in range(3)]

    assert detect(trace(), different_sql)["state"] == "SUCCESS_NO_FINDINGS"
    assert detect(trace(), different_services + different_sql[:3])["state"] == "SUCCESS_NO_FINDINGS"


def test_sequential_and_concurrent_groups_have_deterministic_counts():
    query = "SELECT name FROM product WHERE id = 12"
    sequential = [span(index, query, start=index * 20, end=index * 20 + 10) for index in range(5)]
    concurrent = [span(index, query, start=index, end=100) for index in range(5)]

    sequential_finding = detect(trace(), sequential)["findings"][0]
    concurrent_finding = detect(trace(), concurrent)["findings"][0]

    assert sequential_finding["structured_data"]["sequential_count"] == 5
    assert sequential_finding["severity"] == "MEDIUM"
    assert concurrent_finding["structured_data"]["sequential_count"] == 1
    assert concurrent_finding["severity"] == "LOW"


def database_request(trace_id):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add().resource
    resource.attributes.add(key="service.name").value.string_value = "orders"
    scope = request.resource_spans[0].scope_spans.add()
    parent = scope.spans.add()
    parent.trace_id = bytes.fromhex(trace_id)
    parent.span_id = bytes.fromhex("0000000000000001")
    parent.name = "request"
    parent.kind = Span.SPAN_KIND_SERVER
    parent.start_time_unix_nano = 0
    parent.end_time_unix_nano = 200
    for index in range(5):
        database_span = scope.spans.add()
        database_span.trace_id = bytes.fromhex(trace_id)
        database_span.span_id = (index + 2).to_bytes(8, "big")
        database_span.parent_span_id = parent.span_id
        database_span.name = "SELECT product"
        database_span.kind = Span.SPAN_KIND_CLIENT
        database_span.start_time_unix_nano = index * 20
        database_span.end_time_unix_nano = index * 20 + 10
        database_span.attributes.add(key="db.system.name").value.string_value = "postgresql"
        database_span.attributes.add(key="db.query.text").value.string_value = (
            f"SELECT name FROM product WHERE id = {index}"
        )
    return request


def finalize(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=func.now() - timedelta(seconds=1))
        )
    evaluate_expired_traces()


def analyze(trace_id):
    response = client.post(
        "/v1/traces",
        content=database_request(trace_id).SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    finalize(trace_id)
    assert complete_job(claim_job())


def test_worker_persists_finding_evidence_span_references_and_api():
    trace_id = "0123456789abcdef0123456789abcdef"
    analyze(trace_id)

    with engine.connect() as connection:
        finding = connection.execute(select(findings)).mappings().one()
        evidence_count = connection.execute(select(func.count()).select_from(finding_evidence)).scalar_one()
        span_count = connection.execute(select(func.count()).select_from(finding_spans)).scalar_one()
        result = connection.execute(
            select(detector_results).where(detector_results.c.detector_id == "repeated_database_operation")
        ).mappings().one()
    response = client.get(f"/api/v1/traces/{trace_id}")
    current_run = response.json()["analysis"]["current_run"]

    assert result["state"] == "SUCCESS_WITH_FINDINGS"
    assert finding["finding_type"] == "REPEATED_DATABASE_OPERATION"
    assert finding["structured_data"]["count"] == 5
    assert finding["structured_data"]["combined_duration_ns"] == 50
    assert evidence_count == 3
    assert span_count == 5
    assert len(current_run["findings"][0]["related_span_ids"]) == 5
    assert current_run["findings"][0]["evidence"][0]["structured_data"]["count"] == 5


def test_duplicate_completion_does_not_duplicate_findings():
    trace_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/v1/traces",
        content=database_request(trace_id).SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    finalize(trace_id)
    job = claim_job()

    assert complete_job(job)
    assert not complete_job(job)
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(findings)).scalar_one() == 1


def test_stale_run_findings_are_not_current():
    trace_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/v1/traces",
        content=database_request(trace_id).SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    finalize(trace_id)
    job = claim_job()

    request = database_request(trace_id)
    extra_span = request.resource_spans[0].scope_spans[0].spans.add()
    extra_span.trace_id = bytes.fromhex(trace_id)
    extra_span.span_id = bytes.fromhex("0000000000000009")
    extra_span.parent_span_id = bytes.fromhex("0000000000000001")
    extra_span.name = "late"
    extra_span.kind = Span.SPAN_KIND_INTERNAL
    extra_span.start_time_unix_nano = 210
    extra_span.end_time_unix_nano = 220
    client.post("/v1/traces", content=request.SerializeToString(), headers={"content-type": "application/x-protobuf"})

    assert complete_job(job)
    response = client.get(f"/api/v1/traces/{trace_id}")

    assert response.json()["analysis"]["current_run"] is None
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(findings)).scalar_one() == 1


def test_detector_failure_preserves_canonical_spans(monkeypatch):
    trace_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/v1/traces",
        content=database_request(trace_id).SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    finalize(trace_id)
    job = claim_job()
    with engine.connect() as connection:
        original_count = connection.execute(select(func.count()).select_from(spans)).scalar_one()
    monkeypatch.setattr("traceforge.worker.detect", lambda *_: (_ for _ in ()).throw(RuntimeError("failed")))

    assert complete_job(job)
    with engine.connect() as connection:
        result = connection.execute(
            select(detector_results).where(detector_results.c.detector_id == "repeated_database_operation")
        ).mappings().one()
        current_count = connection.execute(select(func.count()).select_from(spans)).scalar_one()

    assert result["state"] == "FAILED"
    assert current_count == original_count
