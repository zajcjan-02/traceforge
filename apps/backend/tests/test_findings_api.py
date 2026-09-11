from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from traceforge.database import engine
from traceforge.main import app
from traceforge.models import analysis_runs, detector_results, findings, traces

client = TestClient(app)


def add_finding(
    index,
    *,
    finding_type="LIKELY_ERROR_ORIGIN",
    severity="HIGH",
    confidence="HIGH",
    current=True,
    revision=1,
):
    trace_id = index.to_bytes(16, "big")
    run_id = uuid4()
    result_id = uuid4()
    created_at = datetime.now(timezone.utc) + timedelta(seconds=index)
    with engine.begin() as connection:
        connection.execute(traces.insert().values(trace_id=trace_id, revision=revision, first_span_start_ns=0, last_span_end_ns=1, duration_ns=1, span_count=1, completeness_state="COMPLETE", analysis_state="COMPLETE"))
        connection.execute(analysis_runs.insert().values(analysis_run_id=run_id, trace_id=trace_id, trace_revision=1, state="COMPLETE", analysis_version="1", created_at=created_at))
        if current:
            connection.execute(
                traces.update()
                .where(traces.c.trace_id == trace_id)
                .values(current_analysis_run_id=run_id)
            )
        connection.execute(detector_results.insert().values(detector_result_id=result_id, analysis_run_id=run_id, detector_id="test", detector_version="1", state="SUCCESS_WITH_FINDINGS"))
        connection.execute(findings.insert().values(finding_id=uuid4(), analysis_run_id=run_id, trace_id=trace_id, trace_revision=1, detector_result_id=result_id, finding_type=finding_type, severity=severity, confidence=confidence, title=finding_type, summary=str(index), observation="observed", structured_data={"service": "orders"}, created_at=created_at))
    return trace_id.hex()


def test_findings_api_returns_only_current_findings_for_current_trace_revisions():
    current = add_finding(1)
    stale_run = add_finding(2, current=False)
    stale_revision = add_finding(3, revision=2)

    response = client.get("/api/v1/findings")

    assert response.status_code == 200
    assert [item["trace_id"] for item in response.json()["items"]] == [current]
    assert stale_run not in str(response.json())
    assert stale_revision not in str(response.json())


def test_findings_api_orders_filters_and_paginates_without_duplicates():
    database = add_finding(1, finding_type="REPEATED_DATABASE_OPERATION", severity="MEDIUM", confidence="LOW")
    error = add_finding(2)
    downstream = add_finding(3, finding_type="REPEATED_DOWNSTREAM_OPERATION", severity="LOW", confidence="MEDIUM")

    response = client.get("/api/v1/findings?limit=2")
    assert [item["trace_id"] for item in response.json()["items"]] == [downstream, error]
    cursor = response.json()["next_cursor"]
    assert cursor

    continuation = client.get(f"/api/v1/findings?limit=2&cursor={cursor}")
    assert [item["trace_id"] for item in continuation.json()["items"]] == [database]
    assert continuation.json()["next_cursor"] is None

    for query, trace_id in (
        ("type=REPEATED_DATABASE_OPERATION", database),
        ("severity=LOW", downstream),
        ("confidence=HIGH", error),
    ):
        filtered = client.get(f"/api/v1/findings?{query}")
        assert [item["trace_id"] for item in filtered.json()["items"]] == [trace_id]


def test_findings_api_rejects_malformed_cursors():
    response = client.get("/api/v1/findings?cursor=not-a-cursor")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
