from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from traceforge.database import engine
from traceforge.main import app
from traceforge.models import analysis_jobs, traces

client = TestClient(app)


def add_trace(index=1):
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
                completeness_state="COMPLETE",
            )
        )
    return trace_id


def test_system_health_waits_for_first_telemetry():
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {
        "overall_status": "WAITING_FOR_TELEMETRY",
        "backend": {"status": "HEALTHY"},
        "storage": {"status": "HEALTHY"},
        "ingestion": {"status": "WAITING_FOR_TELEMETRY", "last_telemetry_received_at": None},
        "analysis": {
            "status": "HEALTHY",
            "pending_jobs": 0,
            "running_jobs": 0,
            "failed_jobs_recent": 0,
            "oldest_pending_job_age_ms": None,
        },
    }


def test_system_health_reports_telemetry_and_analysis_queue():
    trace_id = add_trace()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            analysis_jobs.insert(),
            [
                {"trace_id": trace_id, "trace_revision": 1, "state": "PENDING", "available_at": now - timedelta(seconds=31), "completed_at": None},
                {"trace_id": trace_id, "trace_revision": 2, "state": "RUNNING", "available_at": now, "completed_at": None},
                {"trace_id": trace_id, "trace_revision": 3, "state": "FAILED", "available_at": now, "completed_at": now},
            ],
        )

    response = client.get("/api/v1/system/health")
    data = response.json()

    assert data["overall_status"] == "DEGRADED"
    assert data["ingestion"]["status"] == "HEALTHY"
    assert data["ingestion"]["last_telemetry_received_at"]
    assert data["analysis"]["status"] == "DEGRADED"
    assert data["analysis"]["pending_jobs"] == 1
    assert data["analysis"]["running_jobs"] == 1
    assert data["analysis"]["failed_jobs_recent"] == 1
    assert data["analysis"]["oldest_pending_job_age_ms"] >= 30_000


def test_system_health_returns_product_status_when_storage_is_unavailable(monkeypatch):
    class UnavailableEngine:
        def connect(self):
            raise OSError("database unavailable")

    monkeypatch.setattr("traceforge.traces.engine", UnavailableEngine())

    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json()["overall_status"] == "UNAVAILABLE"
    assert response.json()["storage"]["status"] == "UNAVAILABLE"
