import asyncio
import os
from datetime import timedelta

from sqlalchemy import delete, exists, func, select, update

from traceforge.database import engine
from traceforge.models import (
    analysis_jobs,
    analysis_runs,
    detector_results,
    finding_evidence,
    finding_spans,
    findings,
    service_dependency_observations,
    span_events,
    spans,
    trace_services,
    traces,
)


def retention_days():
    days = int(os.environ.get("TRACE_RETENTION_DAYS", "7"))
    if days < 0:
        raise ValueError("TRACE_RETENTION_DAYS must be zero or positive")
    return days


def retention_interval():
    interval = int(os.environ.get("TRACE_RETENTION_SWEEP_INTERVAL_SECONDS", "3600"))
    if interval <= 0:
        raise ValueError("TRACE_RETENTION_SWEEP_INTERVAL_SECONDS must be positive")
    return interval


def retention_batch_size():
    size = int(os.environ.get("TRACE_RETENTION_BATCH_SIZE", "200"))
    if size <= 0:
        raise ValueError("TRACE_RETENTION_BATCH_SIZE must be positive")
    return size


def validate_retention_config():
    retention_days()
    retention_interval()
    retention_batch_size()


def eligible_traces(cutoff):
    active_job = exists(
        select(1).where(
            analysis_jobs.c.trace_id == traces.c.trace_id,
            analysis_jobs.c.state.in_(["PENDING", "RUNNING"]),
        )
    )
    return (
        traces.c.completeness_state.in_(["COMPLETE", "INCOMPLETE"]),
        traces.c.last_received_at.is_not(None),
        traces.c.last_received_at < cutoff,
        ~active_job,
    )


def retention_status():
    days = retention_days()
    with engine.connect() as connection:
        now = connection.execute(select(func.now())).scalar_one()
        stored_trace_count = connection.execute(select(func.count()).select_from(traces)).scalar_one()
        if days == 0:
            return {
                "enabled": False,
                "retention_days": 0,
                "cutoff": None,
                "eligible_trace_count": 0,
                "stored_trace_count": stored_trace_count,
            }
        cutoff = now - timedelta(days=days)
        eligible_trace_count = connection.execute(
            select(func.count()).select_from(traces).where(*eligible_traces(cutoff))
        ).scalar_one()
    return {
        "enabled": True,
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "eligible_trace_count": eligible_trace_count,
        "stored_trace_count": stored_trace_count,
    }


def delete_trace(connection, trace_id):
    finding_ids = select(findings.c.finding_id).where(findings.c.trace_id == trace_id)
    run_ids = select(analysis_runs.c.analysis_run_id).where(analysis_runs.c.trace_id == trace_id)

    connection.execute(delete(finding_spans).where(finding_spans.c.trace_id == trace_id))
    connection.execute(delete(finding_evidence).where(finding_evidence.c.finding_id.in_(finding_ids)))
    connection.execute(delete(findings).where(findings.c.trace_id == trace_id))
    connection.execute(delete(detector_results).where(detector_results.c.analysis_run_id.in_(run_ids)))
    connection.execute(delete(span_events).where(span_events.c.trace_id == trace_id))
    connection.execute(delete(spans).where(spans.c.trace_id == trace_id))
    connection.execute(delete(trace_services).where(trace_services.c.trace_id == trace_id))
    connection.execute(delete(service_dependency_observations).where(service_dependency_observations.c.trace_id == trace_id))
    connection.execute(delete(analysis_jobs).where(analysis_jobs.c.trace_id == trace_id))
    connection.execute(
        update(traces).where(traces.c.trace_id == trace_id).values(current_analysis_run_id=None)
    )
    connection.execute(delete(analysis_runs).where(analysis_runs.c.trace_id == trace_id))
    connection.execute(delete(traces).where(traces.c.trace_id == trace_id))


def sweep_retention():
    days = retention_days()
    if days == 0:
        return 0
    size = retention_batch_size()
    with engine.begin() as connection:
        cutoff = connection.execute(select(func.now())).scalar_one() - timedelta(days=days)
        trace_ids = connection.execute(
            select(traces.c.trace_id)
            .where(*eligible_traces(cutoff))
            .order_by(traces.c.last_received_at)
            .limit(size)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        deleted = 0
        for trace_id in trace_ids:
            trace = connection.execute(
                select(traces.c.trace_id)
                .where(traces.c.trace_id == trace_id, *eligible_traces(cutoff))
                .with_for_update()
            ).first()
            if trace is None:
                continue
            delete_trace(connection, trace_id)
            deleted += 1
    return deleted


async def run_retention_sweep():
    interval = retention_interval()
    while True:
        await asyncio.to_thread(run_retention_sweep_once)
        await asyncio.sleep(interval)


def run_retention_sweep_once():
    return sweep_retention()
