import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from traceforge.database import engine
from traceforge.models import analysis_jobs, service_dependency_observations, spans, traces


def completion_deadline():
    seconds = int(os.environ.get("TRACE_QUIET_PERIOD_SECONDS", "2"))
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def evaluate_expired_traces(limit=100):
    with engine.connect() as connection:
        trace_ids = connection.execute(
            select(traces.c.trace_id)
            .where(
                traces.c.completeness_state == "PROCESSING",
                traces.c.completion_deadline <= func.now(),
            )
            .order_by(traces.c.completion_deadline)
            .limit(limit)
        ).scalars()

        for trace_id in trace_ids:
            evaluate_trace(trace_id)


def evaluate_trace(trace_id):
    with engine.begin() as connection:
        trace = connection.execute(
            select(traces)
            .where(
                traces.c.trace_id == trace_id,
                traces.c.completeness_state == "PROCESSING",
                traces.c.completion_deadline <= func.now(),
            )
            .with_for_update()
        ).mappings().first()
        if trace is None:
            return

        trace_spans = connection.execute(
            select(
                spans.c.span_id,
                spans.c.parent_span_id,
                spans.c.service_id,
                spans.c.start_time_unix_ns,
                spans.c.end_time_unix_ns,
            ).where(spans.c.trace_id == trace_id)
        ).mappings().all()
        span_ids = {span["span_id"] for span in trace_spans}
        missing_parent = any(
            span["parent_span_id"] and span["parent_span_id"] not in span_ids
            for span in trace_spans
        )
        root_count = sum(span["parent_span_id"] is None for span in trace_spans)
        invalid_end_time = any(
            span["end_time_unix_ns"] is None
            or span["end_time_unix_ns"] < span["start_time_unix_ns"]
            for span in trace_spans
        )
        state = "INCOMPLETE" if missing_parent or root_count > 1 or invalid_end_time else "COMPLETE"

        spans_by_id = {span["span_id"]: span for span in trace_spans}
        edges = {}
        for child in trace_spans:
            parent = spans_by_id.get(child["parent_span_id"])
            if (
                parent is None
                or parent["service_id"] is None
                or child["service_id"] is None
                or parent["service_id"] == child["service_id"]
            ):
                continue
            edge = (parent["service_id"], child["service_id"])
            edges[edge] = min(edges.get(edge, child["start_time_unix_ns"]), child["start_time_unix_ns"])

        connection.execute(
            delete(service_dependency_observations).where(
                service_dependency_observations.c.trace_id == trace_id
            )
        )
        if edges:
            connection.execute(
                service_dependency_observations.insert(),
                [
                    {
                        "trace_id": trace_id,
                        "source_service_id": source_service_id,
                        "target_service_id": target_service_id,
                        "trace_revision": trace["revision"],
                        "observed_at": observed_at,
                    }
                    for (source_service_id, target_service_id), observed_at in edges.items()
                ],
            )

        connection.execute(
            update(traces)
            .where(traces.c.trace_id == trace_id)
            .values(completeness_state=state, completion_deadline=None)
        )
        job = connection.execute(
            insert(analysis_jobs)
            .values(
                trace_id=trace_id,
                trace_revision=trace["revision"],
                state="PENDING",
            )
            .on_conflict_do_nothing(index_elements=["trace_id", "trace_revision"])
            .returning(analysis_jobs.c.job_id)
        ).first()
        if job is not None:
            connection.execute(
                update(traces)
                .where(
                    traces.c.trace_id == trace_id,
                    traces.c.revision == trace["revision"],
                    traces.c.completeness_state == state,
                )
                .values(analysis_state="PENDING")
            )


async def run_lifecycle_sweep():
    interval = float(os.environ.get("TRACE_LIFECYCLE_SWEEP_INTERVAL_SECONDS", "1"))
    while True:
        await asyncio.to_thread(evaluate_expired_traces)
        await asyncio.sleep(interval)
