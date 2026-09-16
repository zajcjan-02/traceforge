from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from traceforge.database import engine
from traceforge.main import app
from traceforge.models import (
    analysis_runs,
    detector_results,
    findings,
    services,
    spans,
    trace_services,
    traces,
)

client = TestClient(app)


def add_trace(
    index,
    *,
    completeness="COMPLETE",
    received_at=None,
    start=100,
    duration=100,
    roots=((1, "GET /orders", "orders"),),
):
    trace_id = index.to_bytes(16, "big")
    received_at = received_at if received_at is not False else None
    with engine.begin() as connection:
        connection.execute(
            traces.insert().values(
                trace_id=trace_id,
                revision=1,
                first_span_start_ns=start,
                last_span_end_ns=start + duration,
                duration_ns=duration,
                span_count=len(roots),
                completeness_state=completeness,
                last_received_at=received_at,
            )
        )
        for span_id, name, service_name in roots:
            service_id = connection.execute(
                services.select()
                .with_only_columns(services.c.service_id)
                .where(services.c.service_name == service_name, services.c.namespace == "")
            ).scalar()
            if service_id is None:
                service_id = connection.execute(
                    services.insert().values(service_name=service_name, namespace="").returning(services.c.service_id)
                ).scalar_one()
            connection.execute(
                spans.insert().values(
                    trace_id=trace_id,
                    span_id=span_id.to_bytes(8, "big"),
                    service_id=service_id,
                    name=name,
                    span_kind="SERVER",
                    start_time_unix_ns=start,
                    end_time_unix_ns=start + duration,
                    duration_ns=duration,
                    status="UNSET",
                    attributes={},
                    resource_attributes={},
                )
            )
            connection.execute(trace_services.insert().values(trace_id=trace_id, service_id=service_id))
    return trace_id.hex()


def add_current_finding(trace_id, *, severity="HIGH", finding_type="LIKELY_ERROR_ORIGIN", current=True):
    trace_id_bytes = bytes.fromhex(trace_id)
    run_id = uuid4()
    result_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            analysis_runs.insert().values(
                analysis_run_id=run_id,
                trace_id=trace_id_bytes,
                trace_revision=1,
                state="COMPLETE",
                analysis_version="1",
            )
        )
        connection.execute(
            detector_results.insert().values(
                detector_result_id=result_id,
                analysis_run_id=run_id,
                detector_id="test",
                detector_version="1",
                state="SUCCESS_WITH_FINDINGS",
            )
        )
        connection.execute(
            findings.insert().values(
                finding_id=uuid4(),
                analysis_run_id=run_id,
                trace_id=trace_id_bytes,
                trace_revision=1,
                detector_result_id=result_id,
                finding_type=finding_type,
                severity=severity,
                confidence="HIGH",
                title=finding_type,
                summary="summary",
                observation="observation",
                structured_data={},
            )
        )
        if current:
            connection.execute(
                traces.update()
                .where(traces.c.trace_id == trace_id_bytes)
                .values(current_analysis_run_id=run_id, analysis_state="COMPLETE")
            )


def test_root_summary_and_root_operation_filter_are_conservative():
    now = datetime.now(timezone.utc)
    complete = add_trace(1, received_at=now)
    incomplete = add_trace(2, completeness="INCOMPLETE", received_at=now, roots=((1, "GET /orders", "orders"),))
    multiple = add_trace(3, received_at=now, roots=((1, "GET /orders", "orders"), (2, "GET /orders", "payments")))
    missing = add_trace(4, received_at=now, roots=())

    summaries = {item["trace_id"]: item for item in client.get("/api/v1/traces").json()["items"]}

    assert summaries[complete]["root_operation"] == "GET /orders"
    assert summaries[complete]["root_service"]["name"] == "orders"
    assert summaries[incomplete]["root_operation"] is None
    assert summaries[multiple]["root_operation"] is None
    assert summaries[missing]["root_operation"] is None
    assert [item["trace_id"] for item in client.get("/api/v1/traces?root_operation=GET%20%2Forders").json()["items"]] == [complete]


def test_trace_filters_use_current_findings_and_canonical_values():
    now = datetime.now(timezone.utc)
    matching = add_trace(1, received_at=now, start=1_000, duration=500, roots=((1, "GET /orders", "orders"),))
    other = add_trace(2, received_at=now - timedelta(seconds=1), start=2_000, duration=50, roots=((1, "GET /payments", "payments"),))
    add_current_finding(matching, severity="HIGH", finding_type="LIKELY_ERROR_ORIGIN")
    add_current_finding(matching, severity="LOW", finding_type="REPEATED_DATABASE_OPERATION", current=False)

    response = client.get("/api/v1/traces?service_id=1&root_operation=GET%20%2Forders&min_duration_ns=500&max_duration_ns=500&has_findings=true&finding_type=LIKELY_ERROR_ORIGIN&min_severity=MEDIUM&start_time_from_ns=1000&start_time_to_ns=1000")

    assert [item["trace_id"] for item in response.json()["items"]] == [matching]
    summary = response.json()["items"][0]
    assert summary["finding_count"] == 1
    assert summary["highest_finding_severity"] == "HIGH"
    assert [item["trace_id"] for item in client.get("/api/v1/traces?has_findings=false").json()["items"]] == [other]


def test_trace_filters_validate_states_and_exact_trace_ids():
    trace_id = add_trace(1, received_at=datetime.now(timezone.utc))

    assert [item["trace_id"] for item in client.get(f"/api/v1/traces?trace_id={trace_id}").json()["items"]] == [trace_id]
    assert client.get("/api/v1/traces?trace_id=ffffffffffffffffffffffffffffffff").json()["items"] == []
    for query in ("completeness_state=UNKNOWN", "analysis_state=UNKNOWN", "has_findings=yes", "min_duration_ns=20&max_duration_ns=10"):
        assert client.get(f"/api/v1/traces?{query}").status_code == 400


def test_trace_cursor_pages_non_null_and_legacy_receipt_times_without_gaps():
    now = datetime.now(timezone.utc)
    newest = add_trace(4, received_at=now)
    older = add_trace(3, received_at=now - timedelta(seconds=1))
    legacy_high = add_trace(2, received_at=False)
    legacy_low = add_trace(1, received_at=False)
    add_trace(5, completeness="PROCESSING", received_at=now + timedelta(seconds=1))

    first = client.get("/api/v1/traces?limit=2&completeness_state=COMPLETE").json()
    second = client.get(f"/api/v1/traces?limit=2&completeness_state=COMPLETE&cursor={first['next_cursor']}").json()

    assert [item["trace_id"] for item in first["items"]] == [newest, older]
    assert [item["trace_id"] for item in second["items"]] == [legacy_high, legacy_low]
    assert second["next_cursor"] is None
