import base64
import json
from binascii import Error as BinasciiError
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select

from traceforge.database import engine
from traceforge.models import (
    analysis_jobs,
    analysis_runs,
    detector_results,
    finding_evidence,
    finding_spans,
    findings,
    services,
    service_dependency_observations,
    span_events,
    spans,
    trace_services,
    traces,
)

router = APIRouter(prefix="/api/v1")

TIMING_FIELDS = {
    "start_time_unix_ns",
    "end_time_unix_ns",
    "duration_ns",
    "timestamp_unix_ns",
    "first_error_timestamp_unix_ns",
    "error_timestamp_unix_ns",
    "contribution_ns",
    "critical_path_duration_ns",
    "canonical_duration_ns",
    "combined_duration_ns",
}


def trace_bytes(trace_id):
    try:
        value = bytes.fromhex(trace_id)
    except ValueError:
        return None

    return value if len(value) == 16 else None


def serialize_timing_data(data):
    values = dict(data)
    for field in TIMING_FIELDS:
        if field in values and values[field] is not None:
            values[field] = str(values[field])
    for field in ("critical_path_segments", "segments", "chain"):
        if isinstance(values.get(field), list):
            values[field] = [
                serialize_timing_data(item) if isinstance(item, dict) else item
                for item in values[field]
            ]
    return values


def serialize_ns(value):
    return str(value) if value is not None else None


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
                "start_time_unix_ns": serialize_ns(row["first_span_start_ns"]),
                "end_time_unix_ns": serialize_ns(row["last_span_end_ns"]),
                "duration_ns": serialize_ns(row["duration_ns"]),
                "span_count": row["span_count"],
                "service_count": row["service_count"],
                "completeness_state": row["completeness_state"],
                "analysis_state": row["analysis_state"],
            }
            for row in rows
        ]
    }


@router.get("/findings")
def list_findings(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    confidence: str | None = None,
):
    boundary = None
    if cursor:
        try:
            boundary = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if not isinstance(boundary, list) or len(boundary) != 2:
                raise ValueError
            boundary = (datetime.fromisoformat(boundary[0]), UUID(boundary[1]))
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError, BinasciiError):
            return JSONResponse(status_code=400, content={"error": {"code": "INVALID_REQUEST", "message": "Invalid findings cursor."}})
    statement = select(findings, traces.c.current_analysis_run_id).join(
        traces, and_(findings.c.trace_id == traces.c.trace_id, findings.c.analysis_run_id == traces.c.current_analysis_run_id, findings.c.trace_revision == traces.c.revision)
    )
    if type:
        statement = statement.where(findings.c.finding_type == type)
    if severity:
        statement = statement.where(findings.c.severity == severity)
    if confidence:
        statement = statement.where(findings.c.confidence == confidence)
    if boundary:
        created_at, finding_id = boundary
        statement = statement.where(or_(findings.c.created_at < created_at, and_(findings.c.created_at == created_at, findings.c.finding_id < finding_id)))
    statement = statement.order_by(findings.c.created_at.desc(), findings.c.finding_id.desc()).limit(limit + 1)
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
    next_cursor = None
    if len(rows) > limit:
        row = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(json.dumps([row["created_at"].isoformat(), str(row["finding_id"])]).encode()).decode()
        rows = rows[:limit]
    return {"items": [{"finding_id": str(row["finding_id"]), "trace_id": row["trace_id"].hex(), "type": row["finding_type"], "severity": row["severity"], "confidence": row["confidence"], "title": row["title"], "summary": row["summary"], "created_at": row["created_at"].isoformat(), "service": row["structured_data"].get("service") or row["structured_data"].get("source_service")} for row in rows], "next_cursor": next_cursor}


@router.get("/system/health")
def system_health():
    try:
        with engine.connect() as connection:
            now = connection.execute(select(func.now())).scalar_one()
            last_received_at = connection.execute(
                select(func.max(traces.c.last_received_at))
            ).scalar_one()
            pending_jobs = connection.execute(
                select(func.count()).select_from(analysis_jobs).where(
                    analysis_jobs.c.state == "PENDING"
                )
            ).scalar_one()
            running_jobs = connection.execute(
                select(func.count()).select_from(analysis_jobs).where(
                    analysis_jobs.c.state == "RUNNING"
                )
            ).scalar_one()
            failed_jobs_recent = connection.execute(
                select(func.count()).select_from(analysis_jobs).where(
                    analysis_jobs.c.state == "FAILED",
                    analysis_jobs.c.completed_at >= now - timedelta(minutes=15),
                )
            ).scalar_one()
            oldest_pending_at = connection.execute(
                select(func.min(analysis_jobs.c.available_at)).where(
                    analysis_jobs.c.state == "PENDING"
                )
            ).scalar_one()
    except Exception:
        return {
            "overall_status": "UNAVAILABLE",
            "backend": {"status": "HEALTHY"},
            "storage": {"status": "UNAVAILABLE"},
            "ingestion": {"status": "WAITING_FOR_TELEMETRY", "last_telemetry_received_at": None},
            "analysis": {"status": "HEALTHY", "pending_jobs": 0, "running_jobs": 0, "failed_jobs_recent": 0, "oldest_pending_job_age_ms": None},
        }

    oldest_pending_job_age_ms = None
    if oldest_pending_at is not None:
        oldest_pending_job_age_ms = max(0, int((now - oldest_pending_at).total_seconds() * 1000))
    analysis_status = "DEGRADED" if failed_jobs_recent or oldest_pending_job_age_ms is not None and oldest_pending_job_age_ms > 30_000 else "HEALTHY"
    ingestion_status = "HEALTHY" if last_received_at else "WAITING_FOR_TELEMETRY"
    overall_status = "DEGRADED" if analysis_status == "DEGRADED" else ingestion_status
    return {
        "overall_status": overall_status,
        "backend": {"status": "HEALTHY"},
        "storage": {"status": "HEALTHY"},
        "ingestion": {"status": ingestion_status, "last_telemetry_received_at": last_received_at.isoformat() if last_received_at else None},
        "analysis": {"status": analysis_status, "pending_jobs": pending_jobs, "running_jobs": running_jobs, "failed_jobs_recent": failed_jobs_recent, "oldest_pending_job_age_ms": oldest_pending_job_age_ms},
    }


@router.get("/services/{service_id}/dependencies")
def service_dependencies(service_id: int):
    target = services.alias("target")
    source = services.alias("source")
    with engine.connect() as connection:
        service = connection.execute(
            select(services).where(services.c.service_id == service_id)
        ).mappings().first()
        if service is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "SERVICE_NOT_FOUND", "message": "Service not found."}},
            )
        outgoing = connection.execute(
            select(
                target.c.service_id.label("target_service_id"),
                target.c.service_name.label("target_name"),
                target.c.namespace.label("target_namespace"),
                func.count().label("observation_count"),
                func.min(service_dependency_observations.c.observed_at).label("first_seen_at"),
                func.max(service_dependency_observations.c.observed_at).label("last_seen_at"),
            )
            .join(target, target.c.service_id == service_dependency_observations.c.target_service_id)
            .where(service_dependency_observations.c.source_service_id == service_id)
            .group_by(target.c.service_id, target.c.service_name, target.c.namespace)
            .order_by(target.c.service_name, target.c.namespace)
        ).mappings().all()
        incoming = connection.execute(
            select(
                source.c.service_id.label("source_service_id"),
                source.c.service_name.label("source_name"),
                source.c.namespace.label("source_namespace"),
                func.count().label("observation_count"),
                func.min(service_dependency_observations.c.observed_at).label("first_seen_at"),
                func.max(service_dependency_observations.c.observed_at).label("last_seen_at"),
            )
            .join(source, source.c.service_id == service_dependency_observations.c.source_service_id)
            .where(service_dependency_observations.c.target_service_id == service_id)
            .group_by(source.c.service_id, source.c.service_name, source.c.namespace)
            .order_by(source.c.service_name, source.c.namespace)
        ).mappings().all()

    service_data = {"service_id": service["service_id"], "name": service["service_name"], "namespace": service["namespace"]}
    return {
        "outgoing": [
            {
                "source_service": service_data,
                "target_service": {
                    "service_id": row["target_service_id"],
                    "name": row["target_name"],
                    "namespace": row["target_namespace"],
                },
                "observation_count": row["observation_count"],
                "first_seen_at": serialize_ns(row["first_seen_at"]),
                "last_seen_at": serialize_ns(row["last_seen_at"]),
            }
            for row in outgoing
        ],
        "incoming": [
            {
                "source_service": {
                    "service_id": row["source_service_id"],
                    "name": row["source_name"],
                    "namespace": row["source_namespace"],
                },
                "target_service": service_data,
                "observation_count": row["observation_count"],
                "first_seen_at": serialize_ns(row["first_seen_at"]),
                "last_seen_at": serialize_ns(row["last_seen_at"]),
            }
            for row in incoming
        ],
    }


@router.get("/services")
def list_services():
    statement = (
        select(services, func.count(trace_services.c.trace_id).label("trace_count"))
        .outerjoin(trace_services, services.c.service_id == trace_services.c.service_id)
        .group_by(services.c.service_id)
        .order_by(services.c.service_name, services.c.namespace)
    )
    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
    return {"items": [
        {
            "service_id": row["service_id"], "name": row["service_name"], "namespace": row["namespace"],
            "first_seen_at": row["first_seen_at"].isoformat(), "last_seen_at": row["last_seen_at"].isoformat(),
            "trace_count": row["trace_count"],
        }
        for row in rows
    ]}


@router.get("/services/{service_id}")
def get_service(service_id: int):
    all_services = trace_services.alias("all_services")
    with engine.connect() as connection:
        service = connection.execute(select(services).where(services.c.service_id == service_id)).mappings().first()
        if service is None:
            return JSONResponse(status_code=404, content={"error": {"code": "SERVICE_NOT_FOUND", "message": "Service not found."}})
        recent_traces = connection.execute(
            select(traces, func.count(trace_services.c.service_id).label("service_count"))
            .join(trace_services, traces.c.trace_id == trace_services.c.trace_id)
            .where(trace_services.c.service_id == service_id)
            .outerjoin(all_services, traces.c.trace_id == all_services.c.trace_id)
            .group_by(traces.c.trace_id)
            .order_by(traces.c.last_received_at.desc())
            .limit(20)
        ).mappings().all()
    return {
        "service": {
            "service_id": service["service_id"], "name": service["service_name"], "namespace": service["namespace"],
            "first_seen_at": service["first_seen_at"].isoformat(), "last_seen_at": service["last_seen_at"].isoformat(),
        },
        "recent_traces": [
            {
                "trace_id": row["trace_id"].hex(), "revision": row["revision"],
                "start_time_unix_ns": serialize_ns(row["first_span_start_ns"]), "end_time_unix_ns": serialize_ns(row["last_span_end_ns"]),
                "duration_ns": serialize_ns(row["duration_ns"]), "span_count": row["span_count"], "service_count": row["service_count"],
                "completeness_state": row["completeness_state"], "analysis_state": row["analysis_state"],
            }
            for row in recent_traces
        ],
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
        event_rows = connection.execute(
            select(span_events)
            .where(span_events.c.trace_id == trace_id_bytes)
            .order_by(span_events.c.span_id, span_events.c.event_index)
        ).mappings().all()
        events_by_span = {}
        for event in event_rows:
            attributes = {
                key: value
                for key, value in event["attributes"].items()
                if key not in {"exception.message", "exception.stacktrace"}
            }
            events_by_span.setdefault(event["span_id"], []).append(
                {
                    "event_index": event["event_index"],
                    "name": event["name"],
                    "timestamp_unix_ns": (
                        serialize_ns(event["timestamp_unix_ns"])
                    ),
                    "attributes": attributes,
                }
            )
        analysis_run = None
        if trace["current_analysis_run_id"] is not None:
            analysis_run = connection.execute(
                select(analysis_runs).where(
                    analysis_runs.c.analysis_run_id == trace["current_analysis_run_id"],
                    analysis_runs.c.trace_id == trace_id_bytes,
                    analysis_runs.c.trace_revision == trace["revision"],
                )
            ).mappings().first()
        detector_rows = []
        finding_rows = []
        evidence_by_finding = {}
        spans_by_finding = {}
        if analysis_run is not None:
            detector_rows = connection.execute(
                select(detector_results).where(
                    detector_results.c.analysis_run_id == analysis_run["analysis_run_id"]
                )
            ).mappings().all()
            finding_rows = connection.execute(
                select(findings).where(findings.c.analysis_run_id == analysis_run["analysis_run_id"])
            ).mappings().all()
            finding_ids = [finding["finding_id"] for finding in finding_rows]
            if finding_ids:
                evidence_rows = connection.execute(
                    select(finding_evidence).where(finding_evidence.c.finding_id.in_(finding_ids))
                ).mappings().all()
                span_reference_rows = connection.execute(
                    select(finding_spans).where(finding_spans.c.finding_id.in_(finding_ids))
                ).mappings().all()
                for evidence in evidence_rows:
                    evidence_by_finding.setdefault(evidence["finding_id"], []).append(evidence)
                for span_reference in span_reference_rows:
                    spans_by_finding.setdefault(span_reference["finding_id"], []).append(
                        span_reference["span_id"].hex()
                    )

    return {
        "trace": {
            "trace_id": trace["trace_id"].hex(),
            "revision": trace["revision"],
            "start_time_unix_ns": serialize_ns(trace["first_span_start_ns"]),
            "end_time_unix_ns": serialize_ns(trace["last_span_end_ns"]),
            "duration_ns": serialize_ns(trace["duration_ns"]),
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
                    "detector_results": [
                        {
                            "detector_id": result["detector_id"],
                            "detector_version": result["detector_version"],
                            "state": result["state"],
                            "duration_ns": serialize_ns(result["duration_ns"]),
                            "failure_reason": result["failure_reason"],
                        }
                        for result in detector_rows
                    ],
                    "findings": [
                        {
                            "finding_id": str(finding["finding_id"]),
                            "type": finding["finding_type"],
                            "severity": finding["severity"],
                            "confidence": finding["confidence"],
                            "title": finding["title"],
                            "summary": finding["summary"],
                            "observation": finding["observation"],
                            "interpretation": finding["interpretation"],
                            "structured_data": serialize_timing_data(finding["structured_data"]),
                            "related_span_ids": spans_by_finding.get(finding["finding_id"], []),
                            "evidence": [
                                {
                                    "type": evidence["evidence_type"],
                                    "description": evidence["description"],
                                    "structured_data": serialize_timing_data(evidence["structured_data"]),
                                }
                                for evidence in evidence_by_finding.get(finding["finding_id"], [])
                            ],
                        }
                        for finding in finding_rows
                    ],
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
                "start_time_unix_ns": str(span["start_time_unix_ns"]),
                "end_time_unix_ns": (
                    serialize_ns(span["end_time_unix_ns"])
                ),
                "duration_ns": serialize_ns(span["duration_ns"]),
                "status": span["status"],
                "attributes": span["attributes"],
                "resource_attributes": span["resource_attributes"],
                "events": events_by_span.get(span["span_id"], []),
            }
            for span in span_rows
        ],
    }
