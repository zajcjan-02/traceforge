from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from traceforge.database import engine
from traceforge.models import analysis_runs, services, spans, trace_services, traces

router = APIRouter(prefix="/api/v1")


def trace_bytes(trace_id):
    try:
        value = bytes.fromhex(trace_id)
    except ValueError:
        return None

    return value if len(value) == 16 else None


@router.get("/traces")
def list_traces():
    statement = (
        select(traces, func.count(trace_services.c.service_id).label("service_count"))
        .outerjoin(trace_services, traces.c.trace_id == trace_services.c.trace_id)
        .group_by(traces.c.trace_id)
        .order_by(traces.c.last_received_at.desc())
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()

    return {
        "items": [
            {
                "trace_id": row["trace_id"].hex(),
                "revision": row["revision"],
                "start_time_unix_ns": row["first_span_start_ns"],
                "end_time_unix_ns": row["last_span_end_ns"],
                "duration_ns": row["duration_ns"],
                "span_count": row["span_count"],
                "service_count": row["service_count"],
                "completeness_state": row["completeness_state"],
                "analysis_state": row["analysis_state"],
            }
            for row in rows
        ]
    }


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str):
    trace_id_bytes = trace_bytes(trace_id)
    if trace_id_bytes is None:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_TRACE_ID", "message": "Invalid trace ID."}},
        )

    with engine.connect() as connection:
        trace = connection.execute(
            select(traces).where(traces.c.trace_id == trace_id_bytes)
        ).mappings().first()
        if trace is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "TRACE_NOT_FOUND", "message": "Trace not found."}},
            )

        trace_service_rows = connection.execute(
            select(services.c.service_id, services.c.service_name, services.c.namespace)
            .join(trace_services, services.c.service_id == trace_services.c.service_id)
            .where(trace_services.c.trace_id == trace_id_bytes)
            .order_by(services.c.service_name, services.c.namespace)
        ).mappings().all()
        span_rows = connection.execute(
            select(spans, services.c.service_name, services.c.namespace)
            .outerjoin(services, spans.c.service_id == services.c.service_id)
            .where(spans.c.trace_id == trace_id_bytes)
            .order_by(spans.c.start_time_unix_ns, spans.c.span_id)
        ).mappings().all()
        analysis_run = None
        if trace["current_analysis_run_id"] is not None:
            analysis_run = connection.execute(
                select(analysis_runs).where(
                    analysis_runs.c.analysis_run_id == trace["current_analysis_run_id"],
                    analysis_runs.c.trace_id == trace_id_bytes,
                    analysis_runs.c.trace_revision == trace["revision"],
                )
            ).mappings().first()

    return {
        "trace": {
            "trace_id": trace["trace_id"].hex(),
            "revision": trace["revision"],
            "start_time_unix_ns": trace["first_span_start_ns"],
            "end_time_unix_ns": trace["last_span_end_ns"],
            "duration_ns": trace["duration_ns"],
            "span_count": trace["span_count"],
            "completeness_state": trace["completeness_state"],
            "analysis_state": trace["analysis_state"],
            "last_received_at": trace["last_received_at"],
            "services": [
                {
                    "service_id": service["service_id"],
                    "name": service["service_name"],
                    "namespace": service["namespace"],
                }
                for service in trace_service_rows
            ],
        },
        "analysis": {
            "state": trace["analysis_state"],
            "current_run": (
                {
                    "analysis_run_id": str(analysis_run["analysis_run_id"]),
                    "trace_revision": analysis_run["trace_revision"],
                    "state": analysis_run["state"],
                    "started_at": analysis_run["started_at"],
                    "completed_at": analysis_run["completed_at"],
                }
                if analysis_run is not None
                else None
            ),
        },
        "spans": [
            {
                "span_id": span["span_id"].hex(),
                "parent_span_id": span["parent_span_id"].hex()
                if span["parent_span_id"]
                else None,
                "service": (
                    {"name": span["service_name"], "namespace": span["namespace"]}
                    if span["service_name"]
                    else None
                ),
                "name": span["name"],
                "span_kind": span["span_kind"],
                "start_time_unix_ns": span["start_time_unix_ns"],
                "end_time_unix_ns": span["end_time_unix_ns"],
                "duration_ns": span["duration_ns"],
                "status": span["status"],
                "attributes": span["attributes"],
                "resource_attributes": span["resource_attributes"],
            }
            for span in span_rows
        ],
    }
