from datetime import timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from traceforge.database import engine
from traceforge.main import app
from traceforge.models import (
    analysis_jobs,
    analysis_runs,
    detector_results,
    finding_evidence,
    finding_spans,
    findings,
    service_dependency_observations,
    services,
    span_events,
    spans,
    trace_services,
    traces,
)
from traceforge.persistence import persist_spans
from traceforge.retention import retention_batch_size, retention_days, retention_interval, retention_status, sweep_retention

client = TestClient(app)


def add_trace(index, state="COMPLETE", age_days=8):
    trace_id = index.to_bytes(16, "big")
    with engine.begin() as connection:
        connection.execute(
            traces.insert().values(
                trace_id=trace_id,
                revision=1,
                first_span_start_ns=0,
                last_span_end_ns=1,
                duration_ns=1,
                span_count=1,
                completeness_state=state,
                last_received_at=(func.now() - timedelta(days=age_days) if age_days is not None else None),
            )
        )
    return trace_id


def count(table, trace_id):
    column = table.c.trace_id
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(table).where(column == trace_id)).scalar_one()


def test_retention_uses_receipt_time_and_finalized_state(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    old_complete = add_trace(1)
    old_incomplete = add_trace(2, "INCOMPLETE")
    old_processing = add_trace(3, "PROCESSING")
    recent_complete = add_trace(4, age_days=0)

    assert sweep_retention() == 2
    assert count(traces, old_complete) == 0
    assert count(traces, old_incomplete) == 0
    assert count(traces, old_processing) == 1
    assert count(traces, recent_complete) == 1


def test_execution_timestamps_do_not_control_retention(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    trace_id = add_trace(1, age_days=0)
    with engine.begin() as connection:
        connection.execute(
            spans.insert().values(
                trace_id=trace_id,
                span_id=(1).to_bytes(8, "big"),
                name="epoch span",
                span_kind="INTERNAL",
                start_time_unix_ns=0,
                end_time_unix_ns=1,
                duration_ns=1,
                status="UNSET",
                attributes={},
                resource_attributes={},
            )
        )

    assert sweep_retention() == 0
    assert count(traces, trace_id) == 1


def test_unknown_receipt_age_is_not_eligible(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    trace_id = add_trace(1, age_days=None)

    assert sweep_retention() == 0
    assert count(traces, trace_id) == 1


@pytest.mark.parametrize("state", ["PENDING", "RUNNING"])
def test_active_analysis_protects_old_trace(monkeypatch, state):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    trace_id = add_trace(1)
    with engine.begin() as connection:
        connection.execute(analysis_jobs.insert().values(trace_id=trace_id, trace_revision=1, state=state))

    assert sweep_retention() == 0
    assert count(traces, trace_id) == 1


def test_retention_deletes_all_trace_owned_rows_but_keeps_services(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    trace_id = add_trace(1)
    run_id = uuid4()
    result_id = uuid4()
    finding_id = uuid4()
    with engine.begin() as connection:
        service_id = connection.execute(services.insert().values(service_name="orders", namespace="").returning(services.c.service_id)).scalar_one()
        connection.execute(services.insert().values(service_name="payment", namespace=""))
        connection.execute(spans.insert().values(trace_id=trace_id, span_id=(1).to_bytes(8, "big"), service_id=service_id, name="request", span_kind="SERVER", start_time_unix_ns=0, end_time_unix_ns=1, duration_ns=1, status="UNSET", attributes={}, resource_attributes={}))
        connection.execute(span_events.insert().values(trace_id=trace_id, span_id=(1).to_bytes(8, "big"), event_index=0, name="event", attributes={}))
        connection.execute(trace_services.insert().values(trace_id=trace_id, service_id=service_id))
        connection.execute(service_dependency_observations.insert().values(trace_id=trace_id, source_service_id=service_id, target_service_id=service_id + 1, trace_revision=1, observed_at=0))
        connection.execute(analysis_runs.insert().values(analysis_run_id=run_id, trace_id=trace_id, trace_revision=1, state="COMPLETE", analysis_version="test"))
        connection.execute(traces.update().where(traces.c.trace_id == trace_id).values(current_analysis_run_id=run_id))
        connection.execute(analysis_jobs.insert().values(trace_id=trace_id, trace_revision=1, state="COMPLETE"))
        connection.execute(detector_results.insert().values(detector_result_id=result_id, analysis_run_id=run_id, detector_id="test", detector_version="1", state="SUCCESS_NO_FINDINGS"))
        connection.execute(findings.insert().values(finding_id=finding_id, analysis_run_id=run_id, trace_id=trace_id, trace_revision=1, detector_result_id=result_id, finding_type="TEST", severity="LOW", confidence="LOW", title="Test", summary="Test", observation="Test", structured_data={}))
        connection.execute(finding_evidence.insert().values(evidence_id=uuid4(), finding_id=finding_id, evidence_type="TEST", structured_data={}))
        connection.execute(finding_spans.insert().values(finding_id=finding_id, trace_id=trace_id, span_id=(1).to_bytes(8, "big")))

    assert sweep_retention() == 1
    for table in [traces, spans, span_events, trace_services, service_dependency_observations, analysis_jobs, analysis_runs, findings]:
        assert count(table, trace_id) == 0
    with engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(detector_results)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(finding_evidence)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(finding_spans)).scalar_one() == 0
        assert connection.execute(select(func.count()).select_from(services)).scalar_one() == 2


def test_retention_uses_bounded_batches_and_can_be_disabled(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    monkeypatch.setenv("TRACE_RETENTION_BATCH_SIZE", "2")
    for index in range(1, 4):
        add_trace(index)

    assert sweep_retention() == 2
    assert retention_status()["eligible_trace_count"] == 1
    assert sweep_retention() == 1
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "0")
    add_trace(4)
    assert sweep_retention() == 0


def test_retention_configuration_and_api(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "-1")
    with pytest.raises(ValueError):
        retention_days()
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    monkeypatch.setenv("TRACE_RETENTION_SWEEP_INTERVAL_SECONDS", "0")
    with pytest.raises(ValueError):
        retention_interval()
    monkeypatch.setenv("TRACE_RETENTION_SWEEP_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv("TRACE_RETENTION_BATCH_SIZE", "0")
    with pytest.raises(ValueError):
        retention_batch_size()
    monkeypatch.setenv("TRACE_RETENTION_BATCH_SIZE", "200")

    assert client.get("/api/v1/system/retention").json()["stored_trace_count"] == 0
    assert client.post("/api/v1/system/retention/run").json()["deleted_trace_count"] == 0


def test_retention_race_leaves_no_orphan_span(monkeypatch):
    monkeypatch.setenv("TRACE_RETENTION_DAYS", "7")
    trace_id = add_trace(1)
    started = Event()
    release = Event()
    original = __import__("traceforge.retention", fromlist=["delete_trace"]).delete_trace

    def pause_delete(connection, target_trace_id):
        started.set()
        release.wait(2)
        original(connection, target_trace_id)

    monkeypatch.setattr("traceforge.retention.delete_trace", pause_delete)
    retention_thread = Thread(target=sweep_retention)
    retention_thread.start()
    assert started.wait(2)

    span = {
        "trace_id": trace_id,
        "span_id": (1).to_bytes(8, "big"),
        "parent_span_id": None,
        "service_name": "orders",
        "service_namespace": "",
        "name": "late",
        "span_kind": "INTERNAL",
        "start_time_unix_ns": 0,
        "end_time_unix_ns": 1,
        "duration_ns": 1,
        "status": "UNSET",
        "attributes": {},
        "resource_attributes": {},
        "events": [],
    }
    ingestion_thread = Thread(target=persist_spans, args=([span],))
    ingestion_thread.start()
    release.set()
    retention_thread.join(2)
    ingestion_thread.join(2)

    assert count(traces, trace_id) == 1
    assert count(spans, trace_id) == 1
    with engine.connect() as connection:
        assert connection.execute(select(traces.c.completeness_state).where(traces.c.trace_id == trace_id)).scalar_one() == "PROCESSING"
