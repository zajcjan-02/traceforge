from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from traceforge.database import engine
from traceforge.lifecycle import completion_deadline
from traceforge.models import services, span_events, spans, trace_services, traces


def persist_spans(normalized_spans):
    with engine.begin() as connection:
        for span in normalized_spans:
            trace = None
            while trace is None:
                created = connection.execute(
                    insert(traces)
                    .values(
                        trace_id=span["trace_id"],
                        revision=1,
                        first_span_start_ns=span["start_time_unix_ns"],
                        last_span_end_ns=span["end_time_unix_ns"],
                        duration_ns=span["duration_ns"],
                        span_count=1,
                        completeness_state="PROCESSING",
                        completion_deadline=completion_deadline(),
                    )
                    .on_conflict_do_nothing(index_elements=["trace_id"])
                    .returning(traces.c.trace_id)
                ).first()
                trace = connection.execute(
                    select(traces)
                    .where(traces.c.trace_id == span["trace_id"])
                    .with_for_update()
                ).mappings().first()

            service_id = None
            if span["service_name"] is not None:
                service_id = connection.execute(
                    insert(services)
                    .values(
                        service_name=span["service_name"],
                        namespace=span["service_namespace"],
                    )
                    .on_conflict_do_update(
                        index_elements=["service_name", "namespace"],
                        set_={"last_seen_at": func.now()},
                    )
                    .returning(services.c.service_id)
                ).scalar_one()

            inserted = connection.execute(
                insert(spans)
                .values(
                    trace_id=span["trace_id"],
                    span_id=span["span_id"],
                    parent_span_id=span["parent_span_id"],
                    service_id=service_id,
                    name=span["name"],
                    span_kind=span["span_kind"],
                    start_time_unix_ns=span["start_time_unix_ns"],
                    end_time_unix_ns=span["end_time_unix_ns"],
                    duration_ns=span["duration_ns"],
                    status=span["status"],
                    attributes=span["attributes"],
                    resource_attributes=span["resource_attributes"],
                )
                .on_conflict_do_nothing(index_elements=["trace_id", "span_id"])
                .returning(spans.c.span_id)
            ).first()

            if inserted is None:
                continue

            if span["events"]:
                connection.execute(
                    insert(span_events),
                    [
                        {
                            "trace_id": span["trace_id"],
                            "span_id": span["span_id"],
                            **event,
                        }
                        for event in span["events"]
                    ],
                )

            if created is None:
                first_start = min(trace["first_span_start_ns"], span["start_time_unix_ns"])
                end_times = [
                    end_time
                    for end_time in (trace["last_span_end_ns"], span["end_time_unix_ns"])
                    if end_time is not None
                ]
                last_end = max(end_times) if end_times else None
                connection.execute(
                    update(traces)
                    .where(traces.c.trace_id == span["trace_id"])
                    .values(
                        revision=traces.c.revision + 1,
                        first_span_start_ns=first_start,
                        last_span_end_ns=last_end,
                        duration_ns=(last_end - first_start if last_end is not None else None),
                        span_count=traces.c.span_count + 1,
                        completeness_state="PROCESSING",
                        analysis_state=None,
                        current_analysis_run_id=None,
                        last_received_at=func.now(),
                        completion_deadline=completion_deadline(),
                    )
                )

            if service_id is not None:
                connection.execute(
                    insert(trace_services)
                    .values(trace_id=span["trace_id"], service_id=service_id)
                    .on_conflict_do_nothing(index_elements=["trace_id", "service_id"])
                )
