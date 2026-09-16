import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from traceforge_bench.generate import PROFILES, Workload, batches, manifest, trace_id
from traceforge_bench.stats import summary


def arguments():
    parser = argparse.ArgumentParser(description="Run a TraceForge benchmark workload.")
    parser.add_argument("--profile", choices=PROFILES, default="small")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-count", type=int)
    parser.add_argument("--spans-per-trace", type=int)
    parser.add_argument("--service-count", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--target-rate", type=int)
    parser.add_argument("--pattern", default="normal", choices=["normal", "mixed-findings"])
    parser.add_argument("--otlp-endpoint", default="http://127.0.0.1:4318/v1/traces")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--database-url", default=os.environ.get("BENCHMARK_DATABASE_URL", "postgresql://traceforge:traceforge@127.0.0.1:5433/traceforge"))
    parser.add_argument("--poll-interval", type=float, default=1)
    parser.add_argument("--drain-timeout", type=float, default=120)
    parser.add_argument("--analysis-sample", type=int, default=10)
    parser.add_argument("--analysis-timeout", type=float, default=60)
    parser.add_argument("--query-iterations", type=int, default=15)
    parser.add_argument("--quiet-period-seconds", type=int, default=int(os.environ.get("TRACE_QUIET_PERIOD_SECONDS", "2")))
    parser.add_argument("--retention-days", type=int, default=int(os.environ.get("TRACE_RETENTION_DAYS", "7")))
    parser.add_argument("--retention-batch-size", type=int, default=int(os.environ.get("TRACE_RETENTION_BATCH_SIZE", "200")))
    parser.add_argument("--retention", action="store_true")
    parser.add_argument("--docker-stats", action="store_true")
    parser.add_argument("--results-dir", default="bench/results")
    values = parser.parse_args()
    for name in ("trace_count", "spans_per_trace", "service_count", "batch_size", "concurrency"):
        if getattr(values, name) is not None and getattr(values, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if values.target_rate is not None and values.target_rate <= 0:
        parser.error("--target-rate must be positive")
    return values


def workload_from(values):
    profile = PROFILES[values.profile]
    return Workload(
        run_id=values.run_id,
        trace_count=values.trace_count or profile["trace_count"],
        spans_per_trace=values.spans_per_trace or profile["spans_per_trace"],
        service_count=values.service_count or profile["service_count"],
        batch_size=values.batch_size or profile["batch_size"],
        concurrency=values.concurrency or profile["concurrency"],
        target_rate=values.target_rate if values.target_rate is not None else profile["target_rate"],
        pattern=values.pattern,
        base_time_ns=time.time_ns(),
    )


def export_batch(endpoint, payload, trace_count, span_count):
    started = time.perf_counter()
    request = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/x-protobuf"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            accepted = 200 <= response.status < 300
            error = None if accepted else f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exception:
        accepted = False
        error = str(exception)
    return {
        "accepted": accepted,
        "error": error,
        "trace_count": trace_count,
        "span_count": span_count,
        "latency_ms": (time.perf_counter() - started) * 1_000,
    }


def export_workload(workload, endpoint):
    work = list(batches(workload))
    started = time.perf_counter()
    results = []
    submitted_spans = 0
    with ThreadPoolExecutor(max_workers=workload.concurrency) as executor:
        futures = []
        for indexes, payload in work:
            if workload.target_rate:
                target_elapsed = submitted_spans / workload.target_rate
                remaining = target_elapsed - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(remaining)
            span_count = len(indexes) * workload.spans_per_trace
            futures.append(executor.submit(export_batch, endpoint, payload, len(indexes), span_count))
            submitted_spans += span_count
        for future in as_completed(futures):
            results.append(future.result())
    finished = time.perf_counter()
    accepted_spans = sum(result["span_count"] for result in results if result["accepted"])
    return {
        "send_duration_seconds": finished - started,
        "request_latency_ms": summary([result["latency_ms"] for result in results]),
        "export_failures": [result["error"] for result in results if result["error"]],
        "accepted_spans": accepted_spans,
        "attempted_spans": workload.expected_spans,
        "export_throughput_spans_per_second": accepted_spans / (finished - started) if finished > started else None,
        "finished_at": finished,
        "started_at": started,
    }


def manifest_counts(connection, data):
    lower = bytes.fromhex(data["trace_lower_hex"])
    upper = bytes.fromhex(data["trace_upper_hex"])
    trace_count = connection.execute(
        "SELECT count(*) FROM traces WHERE trace_id >= %s AND trace_id < %s", (lower, upper)
    ).fetchone()[0]
    span_count = connection.execute(
        "SELECT count(*) FROM spans WHERE trace_id >= %s AND trace_id < %s", (lower, upper)
    ).fetchone()[0]
    return trace_count, span_count


def wait_for_persistence(database_url, data, expected_spans, interval, timeout, started_at, send_finished_at):
    deadline = time.monotonic() + timeout
    while True:
        with psycopg.connect(database_url) as connection:
            trace_count, span_count = manifest_counts(connection, data)
        confirmed_at = time.perf_counter()
        if span_count >= expected_spans or time.monotonic() >= deadline:
            return {
                "expected_successfully_exported_spans": expected_spans,
                "confirmed_spans": span_count,
                "confirmed_traces": trace_count,
                "post_send_drain_seconds": confirmed_at - send_finished_at,
                "total_end_to_end_ingest_seconds": confirmed_at - started_at,
                "confirmed_persisted_throughput_spans_per_second": span_count / (confirmed_at - started_at) if confirmed_at > started_at else None,
                "settled": span_count >= expected_spans,
            }
        time.sleep(interval)


def request_json(url, method="GET"):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    return json.loads(payload), len(payload)


def benchmark_request(url, iterations):
    try:
        for _ in range(3):
            request_json(url)
    except (urllib.error.URLError, TimeoutError) as error:
        return {"error": str(error)}
    durations = []
    sizes = []
    result_count = None
    for _ in range(iterations):
        started = time.perf_counter()
        try:
            response, size = request_json(url)
        except (urllib.error.URLError, TimeoutError) as error:
            return {"error": str(error), "completed_iterations": len(durations)}
        durations.append((time.perf_counter() - started) * 1_000)
        sizes.append(size)
        result_count = len(response["items"]) if isinstance(response.get("items"), list) else None
    return {"latency_ms": summary(durations), "payload_bytes": summary(sizes), "result_count": result_count}


def service_id(database_url, data):
    lower = bytes.fromhex(data["trace_lower_hex"])
    upper = bytes.fromhex(data["trace_upper_hex"])
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT trace_services.service_id
            FROM trace_services JOIN traces USING (trace_id)
            WHERE traces.trace_id >= %s AND traces.trace_id < %s
            ORDER BY trace_services.service_id LIMIT 1
            """,
            (lower, upper),
        ).fetchone()
    return row[0] if row else None


def benchmark_searches(api_url, database_url, data, iterations):
    base = f"{api_url.rstrip('/')}/api/v1/traces"
    queries = {"unfiltered": {"limit": "50"}, "duration": {"limit": "50", "min_duration_ns": "100000"}, "has_findings": {"limit": "50", "has_findings": "true"}, "finding_type": {"limit": "50", "finding_type": "REPEATED_DATABASE_OPERATION"}}
    current_service = service_id(database_url, data)
    if current_service:
        queries["service"] = {"limit": "50", "service_id": str(current_service)}
        queries["combined"] = {"limit": "50", "service_id": str(current_service), "min_duration_ns": "100000", "has_findings": "true"}
    results = {}
    for name, parameters in queries.items():
        url = f"{base}?{urllib.parse.urlencode(parameters)}"
        results[name] = benchmark_request(url, iterations)
    first, _ = request_json(f"{base}?limit=10")
    cursor = first.get("next_cursor")
    if cursor:
        results["cursor_continuation"] = benchmark_request(f"{base}?{urllib.parse.urlencode({'limit': '10', 'cursor': cursor})}", iterations)
    else:
        results["cursor_continuation"] = {"available": False}
    return results


def benchmark_detail(api_url, workload, iterations):
    identifier = trace_id(workload, 0).hex()
    return benchmark_request(f"{api_url.rstrip('/')}/api/v1/traces/{identifier}", iterations)


def analysis_metrics(database_url, data, target, interval, timeout):
    lower = bytes.fromhex(data["trace_lower_hex"])
    upper = bytes.fromhex(data["trace_upper_hex"])
    deadline = time.monotonic() + timeout
    rows = []
    while True:
        with psycopg.connect(database_url) as connection:
            rows = connection.execute(
                """
                SELECT available_at, claimed_at, completed_at, created_at
                FROM analysis_jobs
                WHERE trace_id >= %s AND trace_id < %s AND state = 'COMPLETE'
                ORDER BY available_at
                LIMIT %s
                """,
                (lower, upper, target),
            ).fetchall()
        if len(rows) >= target or time.monotonic() >= deadline:
            break
        time.sleep(interval)

    def milliseconds(left, right):
        return (right - left).total_seconds() * 1_000 if left and right else None

    queue = [milliseconds(row[0], row[1]) for row in rows]
    worker = [milliseconds(row[1], row[2]) for row in rows]
    end_to_end = [milliseconds(row[0], row[2]) for row in rows]
    scheduling = [milliseconds(row[3], row[0]) for row in rows]
    return {
        "sample_target": target,
        "completed_sample_count": len(rows),
        "scheduling_delay_ms": summary([value for value in scheduling if value is not None]),
        "queue_delay_ms": summary([value for value in queue if value is not None]),
        "worker_held_processing_ms": summary([value for value in worker if value is not None]),
        "eligibility_proxy_to_completion_ms": summary([value for value in end_to_end if value is not None]),
    }


def run_retention(api_url, database_url, data):
    lower = bytes.fromhex(data["trace_lower_hex"])
    upper = bytes.fromhex(data["trace_upper_hex"])
    with psycopg.connect(database_url) as connection:
        aged = connection.execute(
            """
            UPDATE traces
            SET last_received_at = now() - interval '8 days'
            WHERE trace_id >= %s AND trace_id < %s
            """,
            (lower, upper),
        ).rowcount
        connection.commit()
    started = time.perf_counter()
    response, _ = request_json(f"{api_url.rstrip('/')}/api/v1/system/retention/run", method="POST")
    elapsed = (time.perf_counter() - started) * 1_000
    with psycopg.connect(database_url) as connection:
        remaining_traces, remaining_spans = manifest_counts(connection, data)
    return {"aged_benchmark_traces": aged, "deleted_trace_count": response["deleted_trace_count"], "elapsed_ms": elapsed, "remaining_traces": remaining_traces, "remaining_spans": remaining_spans}


def docker_stats():
    container_ids = []
    for service in ("traceforge-backend", "traceforge-worker", "postgres"):
        completed = subprocess.run(
            ["docker", "compose", "ps", "-q", service],
            capture_output=True,
            text=True,
            check=False,
        )
        container_ids.extend(line for line in completed.stdout.splitlines() if line)
    if not container_ids:
        return {"available": False, "error": "No TraceForge Compose containers found."}
    command = ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_ids]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        return {"available": False, "error": completed.stderr.strip()}
    return {"available": True, "samples": [json.loads(line) for line in completed.stdout.splitlines() if line]}


def main():
    values = arguments()
    workload = workload_from(values)
    data = manifest(workload)
    results_dir = Path(values.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = results_dir / f"{workload.run_id}.manifest.json"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    resources_before = docker_stats() if values.docker_stats else None
    exported = export_workload(workload, values.otlp_endpoint)
    persisted = wait_for_persistence(values.database_url, data, exported["accepted_spans"], values.poll_interval, values.drain_timeout, exported["started_at"], exported["finished_at"])
    analysis_target = workload.trace_count if values.retention else min(values.analysis_sample, workload.trace_count)
    analysis = analysis_metrics(values.database_url, data, analysis_target, values.poll_interval, values.analysis_timeout)
    searches = benchmark_searches(values.api_url, values.database_url, data, values.query_iterations)
    detail = benchmark_detail(values.api_url, workload, values.query_iterations)
    retention = run_retention(values.api_url, values.database_url, data) if values.retention else None
    result = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "manifest": data,
        "configuration": {"profile": values.profile, "quiet_period_seconds": values.quiet_period_seconds, "retention_days": values.retention_days, "retention_batch_size": values.retention_batch_size, "poll_interval_seconds": values.poll_interval},
        "export": exported,
        "persistence": persisted,
        "analysis": analysis,
        "search": searches,
        "detail": detail,
        "retention": retention,
        "resources_before": resources_before,
        "resources_after": docker_stats() if values.docker_stats else None,
    }
    output_path = results_dir / f"{workload.run_id}.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved result: {output_path}")


if __name__ == "__main__":
    main()
