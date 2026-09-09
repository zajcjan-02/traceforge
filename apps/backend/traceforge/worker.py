import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update

from traceforge.critical_path import calculate
from traceforge.database import engine
from traceforge.error_origin import (
    DETECTOR_ID as ERROR_ORIGIN_DETECTOR_ID,
    DETECTOR_VERSION as ERROR_ORIGIN_DETECTOR_VERSION,
    detect as detect_error_origin,
)
from traceforge.latency_contributor import (
    DETECTOR_ID as LATENCY_DETECTOR_ID,
    DETECTOR_VERSION as LATENCY_DETECTOR_VERSION,
    detect as detect_latency,
)
from traceforge.models import (
    analysis_jobs,
    analysis_runs,
    detector_results,
    finding_evidence,
    finding_spans,
    findings,
    services,
    span_events,
    spans,
    traces,
)
from traceforge.repeated_database import DETECTOR_ID, DETECTOR_VERSION, detect


def max_attempts():
    return int(os.environ.get("TRACE_ANALYSIS_MAX_ATTEMPTS", "3"))


def reclaim_expired_jobs(connection):
    jobs = connection.execute(
        select(analysis_jobs)
        .where(
            analysis_jobs.c.state == "RUNNING",
            analysis_jobs.c.lease_expires_at < func.now(),
        )
        .with_for_update(skip_locked=True)
    ).mappings()
    for job in jobs:
        if job["attempt_count"] >= max_attempts():
            connection.execute(
                update(analysis_jobs)
                .where(
                    analysis_jobs.c.job_id == job["job_id"],
                    analysis_jobs.c.state == "RUNNING",
                    analysis_jobs.c.claim_token == job["claim_token"],
                )
                .values(state="FAILED", completed_at=func.now())
            )
            connection.execute(
                update(traces)
                .where(
                    traces.c.trace_id == job["trace_id"],
                    traces.c.revision == job["trace_revision"],
                )
                .values(analysis_state="FAILED")
            )
        else:
            connection.execute(
                update(analysis_jobs)
                .where(
                    analysis_jobs.c.job_id == job["job_id"],
                    analysis_jobs.c.state == "RUNNING",
                    analysis_jobs.c.claim_token == job["claim_token"],
                )
                .values(
                    state="PENDING",
                    available_at=func.now(),
                    claimed_at=None,
                    lease_expires_at=None,
                    claim_token=None,
                )
            )


def claim_job():
    with engine.begin() as connection:
        reclaim_expired_jobs(connection)
        job = connection.execute(
            select(analysis_jobs)
            .where(
                analysis_jobs.c.state == "PENDING",
                analysis_jobs.c.available_at <= func.now(),
            )
            .order_by(analysis_jobs.c.available_at, analysis_jobs.c.job_id)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).mappings().first()
        if job is None:
            return None

        token = uuid4()
        lease_seconds = int(os.environ.get("TRACE_ANALYSIS_LEASE_SECONDS", "30"))
        connection.execute(
            update(analysis_jobs)
            .where(analysis_jobs.c.job_id == job["job_id"])
            .values(
                state="RUNNING",
                attempt_count=analysis_jobs.c.attempt_count + 1,
                claimed_at=func.now(),
                lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=lease_seconds),
                claim_token=token,
            )
        )
        connection.execute(
            update(traces)
            .where(
                traces.c.trace_id == job["trace_id"],
                traces.c.revision == job["trace_revision"],
            )
            .values(analysis_state="RUNNING")
        )

    return {**job, "claim_token": token, "attempt_count": job["attempt_count"] + 1}


def load_trace(job):
    with engine.connect() as connection:
        trace = connection.execute(
            select(traces).where(traces.c.trace_id == job["trace_id"])
        ).mappings().first()
        span_rows = connection.execute(
            select(spans, services.c.service_name)
            .outerjoin(services, spans.c.service_id == services.c.service_id)
            .where(spans.c.trace_id == job["trace_id"])
        ).mappings().all()
        event_rows = connection.execute(
            select(span_events).where(span_events.c.trace_id == job["trace_id"])
        ).mappings().all()
    if trace is None:
        raise ValueError("Trace revision is unavailable")
    return trace, span_rows, event_rows


def run_detector(detector, *args):
    started_at = time.perf_counter_ns()
    try:
        return detector(*args), time.perf_counter_ns() - started_at, None
    except Exception as error:
        return {"state": "FAILED", "findings": []}, time.perf_counter_ns() - started_at, str(error)


def complete_job(job):
    trace, span_rows, event_rows = load_trace(job)
    critical_path = (
        calculate(trace, span_rows)
        if trace["revision"] == job["trace_revision"]
        else {"state": "UNAVAILABLE"}
    )
    outcomes = [
        (LATENCY_DETECTOR_ID, LATENCY_DETECTOR_VERSION, *run_detector(detect_latency, trace, span_rows, critical_path)),
        (DETECTOR_ID, DETECTOR_VERSION, *run_detector(detect, trace, span_rows)),
        (ERROR_ORIGIN_DETECTOR_ID, ERROR_ORIGIN_DETECTOR_VERSION, *run_detector(detect_error_origin, trace, span_rows, event_rows)),
    ]

    with engine.begin() as connection:
        current_job = connection.execute(
            select(analysis_jobs)
            .where(
                analysis_jobs.c.job_id == job["job_id"],
                analysis_jobs.c.state == "RUNNING",
                analysis_jobs.c.claim_token == job["claim_token"],
            )
            .with_for_update()
        ).mappings().first()
        if current_job is None:
            return False

        run_id = uuid4()
        run_state = "FAILED" if any(outcome[2]["state"] == "FAILED" for outcome in outcomes) else "COMPLETE"
        connection.execute(
            analysis_runs.insert().values(
                analysis_run_id=run_id,
                trace_id=current_job["trace_id"],
                trace_revision=current_job["trace_revision"],
                state=run_state,
                analysis_version="latency-contributor-v1,repeated-database-v1,error-origin-v1",
                completed_at=func.now(),
            )
        )
        for detector_id, detector_version, outcome, duration_ns, failure_reason in outcomes:
            result_id = uuid4()
            connection.execute(
                detector_results.insert().values(
                    detector_result_id=result_id,
                    analysis_run_id=run_id,
                    detector_id=detector_id,
                    detector_version=detector_version,
                    state=outcome["state"],
                    duration_ns=duration_ns,
                    failure_reason=failure_reason,
                )
            )
            for finding in outcome["findings"]:
                finding_id = uuid4()
                connection.execute(
                    findings.insert().values(
                        finding_id=finding_id,
                        analysis_run_id=run_id,
                        trace_id=current_job["trace_id"],
                        trace_revision=current_job["trace_revision"],
                        detector_result_id=result_id,
                        finding_type=finding["type"],
                        severity=finding["severity"],
                        confidence=finding["confidence"],
                        title=finding["title"],
                        summary=finding["summary"],
                        observation=finding["observation"],
                        interpretation=finding["interpretation"],
                        structured_data=finding["structured_data"],
                    )
                )
                connection.execute(
                    finding_evidence.insert(),
                    [
                        {
                            "evidence_id": uuid4(),
                            "finding_id": finding_id,
                            "evidence_type": evidence["type"],
                            "structured_data": evidence["structured_data"],
                        }
                        for evidence in finding["evidence"]
                    ],
                )
                references = finding.get("span_relations")
                if references is None:
                    references = [
                        {"span": span, "relation": finding["relation"]} for span in finding["spans"]
                    ]
                connection.execute(
                    finding_spans.insert(),
                    [
                        {
                            "finding_id": finding_id,
                            "trace_id": current_job["trace_id"],
                            "span_id": reference["span"]["span_id"],
                            "relation": reference["relation"],
                        }
                        for reference in references
                    ],
                )
        connection.execute(
            update(analysis_jobs)
            .where(
                analysis_jobs.c.job_id == current_job["job_id"],
                analysis_jobs.c.state == "RUNNING",
                analysis_jobs.c.claim_token == current_job["claim_token"],
            )
            .values(state="COMPLETE", completed_at=func.now(), lease_expires_at=None)
        )
        trace_update = update(traces).where(
            traces.c.trace_id == current_job["trace_id"],
            traces.c.revision == current_job["trace_revision"],
        )
        if run_state == "FAILED":
            connection.execute(trace_update.values(analysis_state="FAILED", current_analysis_run_id=None))
        else:
            connection.execute(
                trace_update.values(analysis_state="COMPLETE", current_analysis_run_id=run_id)
            )
    return True


def fail_job(job, error):
    with engine.begin() as connection:
        current_job = connection.execute(
            select(analysis_jobs)
            .where(
                analysis_jobs.c.job_id == job["job_id"],
                analysis_jobs.c.state == "RUNNING",
                analysis_jobs.c.claim_token == job["claim_token"],
            )
            .with_for_update()
        ).mappings().first()
        if current_job is None:
            return

        failed = current_job["attempt_count"] >= max_attempts()
        connection.execute(
            update(analysis_jobs)
            .where(
                analysis_jobs.c.job_id == current_job["job_id"],
                analysis_jobs.c.claim_token == current_job["claim_token"],
            )
            .values(
                state="FAILED" if failed else "PENDING",
                available_at=func.now(),
                completed_at=func.now() if failed else None,
                claimed_at=None if not failed else current_job["claimed_at"],
                lease_expires_at=None,
                claim_token=None,
                last_error=str(error),
            )
        )
        if failed:
            connection.execute(
                update(traces)
                .where(
                    traces.c.trace_id == current_job["trace_id"],
                    traces.c.revision == current_job["trace_revision"],
                )
                .values(analysis_state="FAILED")
            )


def run_once():
    job = claim_job()
    if job is None:
        return False
    try:
        complete_job(job)
    except Exception as error:
        fail_job(job, error)
    return True


def run_worker():
    interval = float(os.environ.get("TRACE_ANALYSIS_POLL_SECONDS", "1"))
    while True:
        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    run_worker()
