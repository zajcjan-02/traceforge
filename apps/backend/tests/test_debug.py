from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from traceforge.database import engine
from traceforge.lifecycle import evaluate_expired_traces
from traceforge.main import app
from traceforge.models import traces
from traceforge.worker import claim_job, complete_job

client = TestClient(app)


def finish(trace_id):
    with engine.begin() as connection:
        connection.execute(
            update(traces)
            .where(traces.c.trace_id == bytes.fromhex(trace_id))
            .values(completion_deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
    evaluate_expired_traces()
    assert complete_job(claim_job())


def test_debug_routes_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TRACEFORGE_DEBUG_UI", raising=False)

    assert client.get("/debug").status_code == 404
    assert client.post("/debug/generate/normal").status_code == 404
    assert client.post("/debug/generate/latency-contributor").status_code == 404
    assert client.get("/debug/critical-path/0123456789abcdef0123456789abcdef").status_code == 404


def test_debug_page_and_normal_scenario(monkeypatch):
    monkeypatch.setenv("TRACEFORGE_DEBUG_UI", "true")

    page = client.get("/debug")
    created = client.post("/debug/generate/normal")
    trace_id = created.json()["trace_id"]
    finish(trace_id)
    detail = client.get(f"/api/v1/traces/{trace_id}").json()

    assert page.status_code == 200
    assert "Generate normal trace" in page.text
    assert "Generate critical-path trace" in page.text
    assert "Generate latency-contributor trace" in page.text
    assert "Raw JSON" in page.text
    assert detail["trace"]["completeness_state"] == "COMPLETE"
    assert detail["analysis"]["state"] == "COMPLETE"
    assert detail["analysis"]["current_run"]["findings"] == []


def test_repeated_database_scenario_creates_a_finding(monkeypatch):
    monkeypatch.setenv("TRACEFORGE_DEBUG_UI", "true")

    created = client.post("/debug/generate/repeated-db")
    trace_id = created.json()["trace_id"]
    finish(trace_id)
    detail = client.get(f"/api/v1/traces/{trace_id}").json()
    finding = detail["analysis"]["current_run"]["findings"][0]

    assert detail["trace"]["span_count"] == 7
    assert finding["type"] == "REPEATED_DATABASE_OPERATION"
    assert finding["structured_data"]["count"] == 5


def test_critical_path_scenario_displays_deterministic_segments(monkeypatch):
    monkeypatch.setenv("TRACEFORGE_DEBUG_UI", "true")

    trace_id = client.post("/debug/generate/critical-path").json()["trace_id"]
    finish(trace_id)
    result = client.get(f"/debug/critical-path/{trace_id}").json()

    assert result["state"] == "AVAILABLE"
    assert result["duration_ns"] == 1000
    assert [
        (segment["span_id"], segment["start_time_unix_ns"], segment["end_time_unix_ns"])
        for segment in result["segments"]
    ] == [
        ("0000000000000001", 0, 100),
        ("0000000000000002", 100, 200),
        ("0000000000000003", 200, 900),
        ("0000000000000001", 900, 1000),
    ]


def test_latency_contributor_scenario_creates_a_finding(monkeypatch):
    monkeypatch.setenv("TRACEFORGE_DEBUG_UI", "true")

    trace_id = client.post("/debug/generate/latency-contributor").json()["trace_id"]
    finish(trace_id)
    detail = client.get(f"/api/v1/traces/{trace_id}").json()
    finding = next(
        finding
        for finding in detail["analysis"]["current_run"]["findings"]
        if finding["type"] == "MAJOR_LATENCY_CONTRIBUTOR"
    )

    assert finding["structured_data"]["service"] == "debug-payment"
    assert finding["structured_data"]["contribution_ns"] == 2_300_000_000
    assert finding["structured_data"]["critical_path_duration_ns"] == 3_000_000_000
    assert finding["structured_data"]["canonical_duration_ns"] == 2_300_000_000
    assert finding["related_span_ids"] == ["0000000000000002"]
    assert next(
        result
        for result in detail["analysis"]["current_run"]["detector_results"]
        if result["detector_id"] == "latency_contributor"
    )["state"] == "SUCCESS_WITH_FINDINGS"
    assert {evidence["type"] for evidence in finding["evidence"]} == {
        "CRITICAL_PATH_CONTRIBUTION",
        "CRITICAL_PATH_SEGMENTS",
    }
