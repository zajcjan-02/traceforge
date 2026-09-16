# TraceForge benchmarks

These benchmarks export ordinary OTLP protobuf trace batches to the local
Collector and confirm persistence through PostgreSQL. They never write
telemetry using TraceForge application internals.

## Setup

Start a stable local stack first:

```sh
docker compose up --build
```

Install benchmark dependencies once:

```sh
cd bench
pip install -e ".[dev]"
```

## Run a profile

Run from the repository root. `run_id` identifies only this run's trace-ID
range, allowing persistence confirmation and retention aging to ignore prior
data.

```sh
python bench/run_benchmarks.py --profile small --run-id small-baseline-001
python bench/run_benchmarks.py --profile medium --run-id medium-baseline-001
```

Profiles:

- `small`: 1,000 traces × 10 spans (10,000 spans).
- `medium`: 10,000 traces × 15 spans (150,000 spans).
- `large`: 100,000 traces × 10 spans (1,000,000 spans); optional for a
  developer machine.
- `retention`: 20 traces × 10 spans and one normal retention sweep.

Useful overrides keep detail-query measurements reproducible at different
trace sizes:

```sh
python bench/run_benchmarks.py --profile small --run-id detail-100 \
  --trace-count 20 --spans-per-trace 100
python bench/run_benchmarks.py --profile small --run-id detail-500 \
  --trace-count 10 --spans-per-trace 500
```

The runner writes a manifest and result JSON to `bench/results/`. Result files
record profile, batch size, concurrency, requested rate, spans per trace,
service count, quiet period, and retention settings.

## Measurements

`export_throughput_spans_per_second` measures accepted OTLP spans over the
generator's send interval. `confirmed_persisted_throughput_spans_per_second`
measures manifest spans confirmed in PostgreSQL from benchmark start through
Collector/backend drain. The report includes send duration, drain duration,
end-to-end duration, expected/confirmed counts, and export failures.

Analysis fields deliberately separate queue delay (`available_at` to
`claimed_at`), worker-held processing (`claimed_at` to `completed_at`), and
the eligibility proxy (`available_at` to `completed_at`). `available_at` is
the persisted scheduling proxy, not an exact trace-finalization timestamp.

## Retention

Run the retention profile with a normal TraceForge retention configuration:

```sh
python bench/run_benchmarks.py --profile retention --run-id retention-001 --retention
```

Only trace IDs in that run's manifest are aged by the benchmark runner. It
then calls the normal `POST /api/v1/system/retention/run` endpoint; it does
not implement a separate cleanup path. Do not use this mode against telemetry
you need to retain.

## Resource snapshots

Add `--docker-stats` for before/after Docker CPU and memory snapshots. These
are coarse local observations, not continuous profiling.
