import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update

from traceforge.database import engine
from traceforge.models import analysis_jobs, analysis_runs, traces


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


def complete_job(job):
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
        connection.execute(
            analysis_runs.insert().values(
                analysis_run_id=run_id,
                trace_id=current_job["trace_id"],
                trace_revision=current_job["trace_revision"],
                state="COMPLETE",
                analysis_version="empty",
                completed_at=func.now(),
            )
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
        connection.execute(
            update(traces)
            .where(
                traces.c.trace_id == current_job["trace_id"],
                traces.c.revision == current_job["trace_revision"],
            )
            .values(analysis_state="COMPLETE", current_analysis_run_id=run_id)
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
