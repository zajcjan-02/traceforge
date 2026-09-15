from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import analysis_jobs, analysis_runs, traces
from traceforge.worker import claim_job, complete_job

client = TestClient(app)


def request_with_span(trace_id, span_id, parent_span_id=None):
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
    span.end_time_unix_nano = 250
    return request


def send(request):
    return client.post(
        "/v1/traces",
        content=request.SerializeToString(),
        headers={"content-type": "application/x-protobuf"},
    )


def row(table, trace_id):
    with engine.connect() as connection:
        return connection.execute(
            select(table).where(table.c.trace_id == bytes.fromhex(trace_id))
        ).mappings().one()


def finalize(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=func.now() - timedelta(seconds=1))
        )
    evaluate_expired_traces()


def test_finalization_creates_one_pending_job():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))

    finalize(trace_id)
    evaluate_expired_traces()

    job = row(analysis_jobs, trace_id)
    assert job["trace_revision"] == 1
    assert job["state"] == "PENDING"
    assert row(traces, trace_id)["analysis_state"] == "PENDING"


def test_worker_completes_current_revision_and_exposes_it():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)

    job = claim_job()
    assert row(traces, trace_id)["analysis_state"] == "RUNNING"
    assert complete_job(job)

    trace = row(traces, trace_id)
    run = row(analysis_runs, trace_id)
    response = client.get(f"/api/v1/traces/{trace_id}")
    list_response = client.get("/api/v1/traces")

    assert trace["analysis_state"] == "COMPLETE"
    assert trace["current_analysis_run_id"] == run["analysis_run_id"]
    assert run["trace_revision"] == trace["revision"]
    assert response.json()["analysis"]["current_run"]["analysis_run_id"] == str(run["analysis_run_id"])
    assert list_response.json()["items"][0]["analysis_state"] == "COMPLETE"


def test_worker_calculates_critical_path_for_current_revision(monkeypatch):
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)
    calculated = []
    monkeypatch.setattr("traceforge.worker.calculate", lambda trace, spans: calculated.append((trace, spans)))

    assert complete_job(claim_job())
    assert len(calculated) == 1


def test_only_one_worker_can_claim_a_job():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)

    assert claim_job() is not None
    assert claim_job() is None


def test_expired_lease_is_reclaimed_with_a_new_claim_token():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)
    first_job = claim_job()

    with engine.begin() as connection:
        connection.execute(
            update(analysis_jobs)
            .where(analysis_jobs.c.job_id == first_job["job_id"])
            .values(lease_expires_at=func.now() - timedelta(seconds=1))
        )
    second_job = claim_job()

    assert second_job["job_id"] == first_job["job_id"]
    assert second_job["claim_token"] != first_job["claim_token"]
    assert second_job["attempt_count"] == 2


def test_lost_claim_cannot_publish_an_analysis_run():
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)
    job = claim_job()

    with engine.begin() as connection:
        connection.execute(
            update(analysis_jobs)
            .where(analysis_jobs.c.job_id == job["job_id"])
            .values(claim_token=uuid4())
        )

    assert not complete_job(job)
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(analysis_runs)).scalar_one() == 0


def test_exhausted_expired_job_marks_current_trace_failed(monkeypatch):
    monkeypatch.setenv("TRACE_ANALYSIS_MAX_ATTEMPTS", "1")
    trace_id = "0123456789abcdef0123456789abcdef"
    send(request_with_span(trace_id, "0123456789abcdef"))
    finalize(trace_id)
    job = claim_job()

    with engine.begin() as connection:
        connection.execute(
            update(analysis_jobs)
            .where(analysis_jobs.c.job_id == job["job_id"])
            .values(lease_expires_at=func.now() - timedelta(seconds=1))
        )

    assert claim_job() is None
    assert row(analysis_jobs, trace_id)["state"] == "FAILED"
    assert row(traces, trace_id)["analysis_state"] == "FAILED"


def test_late_span_clears_current_analysis_and_schedules_next_revision():
    trace_id = "0123456789abcdef0123456789abcdef"
    first_span_id = "0123456789abcdef"
    send(request_with_span(trace_id, first_span_id))
    finalize(trace_id)
    complete_job(claim_job())

    send(request_with_span(trace_id, "fedcba9876543210", first_span_id))
    reopened = row(traces, trace_id)

    assert reopened["revision"] == 2
    assert reopened["analysis_state"] is None
    assert reopened["current_analysis_run_id"] is None

    finalize(trace_id)
    with engine.connect() as connection:
        job = connection.execute(
            select(analysis_jobs).where(
                analysis_jobs.c.trace_id == bytes.fromhex(trace_id),
                analysis_jobs.c.trace_revision == 2,
            )
        ).mappings().one()
    assert job["state"] == "PENDING"


def test_old_revision_run_is_not_published_as_current():
    trace_id = "0123456789abcdef0123456789abcdef"
    first_span_id = "0123456789abcdef"
    send(request_with_span(trace_id, first_span_id))
    finalize(trace_id)
    job = claim_job()

    send(request_with_span(trace_id, "fedcba9876543210", first_span_id))
    assert complete_job(job)

    trace = row(traces, trace_id)
    assert trace["revision"] == 2
    assert trace["current_analysis_run_id"] is None
    assert trace["analysis_state"] is None
