"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { findingTypeLabels, type Service, type TraceSummary } from "../lib/api";
import { formatDuration, formatTimestamp } from "../lib/timing";

const units: Record<string, bigint> = { ns: 1n, "µs": 1_000n, ms: 1_000_000n, s: 1_000_000_000n };

function timeValue(value: string | undefined) {
  if (!value) return "";
  const milliseconds = BigInt(value) / 1_000_000n;
  if (milliseconds > BigInt(Number.MAX_SAFE_INTEGER)) return "";
  return new Date(Number(milliseconds)).toISOString().slice(0, 16);
}

function timeNs(value: string) {
  if (!value) return "";
  const milliseconds = Date.parse(value);
  return Number.isNaN(milliseconds) ? null : (BigInt(milliseconds) * 1_000_000n).toString();
}

export function TraceList({
  traces,
  services,
  filters,
  nextHref,
}: {
  traces: TraceSummary[];
  services: Service[];
  filters: Record<string, string | undefined>;
  nextHref: string | null;
}) {
  const router = useRouter();
  const [scenario, setScenario] = useState("normal");
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [minDuration, setMinDuration] = useState(filters.min_duration_ns ?? "");
  const [maxDuration, setMaxDuration] = useState(filters.max_duration_ns ?? "");
  const [minUnit, setMinUnit] = useState("ns");
  const [maxUnit, setMaxUnit] = useState("ns");
  const hasFilters = Object.entries(filters).some(([key, value]) => key !== "order" && key !== "cursor" && Boolean(value));

  async function generateTrace() {
    setGenerating(true);
    setMessage("");
    try {
      const response = await fetch(`/api/debug/generate/${scenario}`, { method: "POST" });
      if (!response.ok) throw new Error();
      setMessage("Debug trace generated. Refreshing list…");
      router.refresh();
    } catch {
      setMessage("Debug trace generation is unavailable.");
    } finally {
      setGenerating(false);
    }
  }

  function applyFilters(form: HTMLFormElement) {
    const values = new FormData(form);
    const params = new URLSearchParams();
    setError("");
    for (const key of ["trace_id", "service_id", "root_operation", "completeness_state", "analysis_state", "has_findings", "finding_type", "min_severity", "order"]) {
      const value = values.get(key)?.toString();
      if (value) params.set(key, value);
    }
    for (const [name, value, unit] of [["min_duration_ns", minDuration, minUnit], ["max_duration_ns", maxDuration, maxUnit]] as const) {
      if (!value) continue;
      if (!/^\d+$/.test(value)) {
        setError("Duration filters must be whole numbers.");
        return;
      }
      params.set(name, (BigInt(value) * units[unit]).toString());
    }
    for (const [name, value] of [["start_time_from_ns", values.get("start_from")?.toString() ?? ""], ["start_time_to_ns", values.get("start_to")?.toString() ?? ""]]) {
      const converted = timeNs(value);
      if (converted === null) {
        setError("Execution time filters must be valid local date-times.");
        return;
      }
      if (converted) params.set(name, converted);
    }
    router.push(`/traces${params.size ? `?${params}` : ""}`);
  }

  return (
    <>
      <form className="mb-4 grid gap-3 rounded-md border border-forge-border bg-forge-panel p-3 text-sm md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); applyFilters(event.currentTarget); }}>
        <input aria-label="Trace ID" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.trace_id} name="trace_id" placeholder="Exact trace ID" />
        <select aria-label="Service" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.service_id} name="service_id"><option value="">All services</option>{services.map((service) => <option key={service.service_id} value={service.service_id}>{service.name}{service.namespace ? ` (${service.namespace})` : ""}</option>)}</select>
        <input aria-label="Root operation" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.root_operation} name="root_operation" placeholder="Exact root operation" />
        <select aria-label="Completeness" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.completeness_state} name="completeness_state"><option value="">All completeness states</option><option>PROCESSING</option><option>COMPLETE</option><option>INCOMPLETE</option></select>
        <select aria-label="Analysis state" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.analysis_state} name="analysis_state"><option value="">All analysis states</option><option value="NULL">No stored analysis state</option><option>PENDING</option><option>RUNNING</option><option>COMPLETE</option><option>PARTIAL</option><option>FAILED</option></select>
        <label className="flex gap-1"><input aria-label="Minimum duration" className="min-w-0 flex-1 rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" min="0" onChange={(event) => setMinDuration(event.target.value)} placeholder="Min duration" type="number" value={minDuration} /><select aria-label="Minimum duration unit" className="rounded border border-forge-border bg-forge-base px-1 text-forge-text" onChange={(event) => setMinUnit(event.target.value)} value={minUnit}>{Object.keys(units).map((unit) => <option key={unit}>{unit}</option>)}</select></label>
        <label className="flex gap-1"><input aria-label="Maximum duration" className="min-w-0 flex-1 rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" min="0" onChange={(event) => setMaxDuration(event.target.value)} placeholder="Max duration" type="number" value={maxDuration} /><select aria-label="Maximum duration unit" className="rounded border border-forge-border bg-forge-base px-1 text-forge-text" onChange={(event) => setMaxUnit(event.target.value)} value={maxUnit}>{Object.keys(units).map((unit) => <option key={unit}>{unit}</option>)}</select></label>
        <select aria-label="Has findings" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.has_findings} name="has_findings"><option value="">Any findings state</option><option value="true">Has findings</option><option value="false">No findings</option></select>
        <select aria-label="Finding type" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.finding_type} name="finding_type"><option value="">All finding types</option>{Object.entries(findingTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select aria-label="Minimum finding severity" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.min_severity} name="min_severity"><option value="">Any severity</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select>
        <label className="text-forge-muted">Start from<input aria-label="Start time from" className="mt-1 block w-full rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={timeValue(filters.start_time_from_ns)} name="start_from" type="datetime-local" /></label>
        <label className="text-forge-muted">Start to<input aria-label="Start time to" className="mt-1 block w-full rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={timeValue(filters.start_time_to_ns)} name="start_to" type="datetime-local" /></label>
        <select aria-label="Order" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" defaultValue={filters.order ?? "received_desc"} name="order"><option value="received_desc">Newest received first</option><option value="received_asc">Oldest received first</option></select>
        <div className="flex items-center gap-3"><button className="rounded border border-forge-accent/60 px-3 py-1 text-forge-accent hover:bg-forge-base" type="submit">Apply filters</button>{hasFilters && <Link className="text-forge-muted hover:text-forge-text" href="/traces">Clear filters</Link>}</div>
        {error && <p className="text-forge-highlight md:col-span-4">{error}</p>}
      </form>
      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-forge-border bg-forge-panel p-3 text-sm">
        <span className="text-forge-muted">Debug</span>
        <select aria-label="Debug trace scenario" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" onChange={(event) => setScenario(event.target.value)} value={scenario}>
          <option value="normal">Normal trace</option><option value="repeated-db">Repeated database</option><option value="critical-path">Critical path</option><option value="latency-contributor">Latency contributor</option><option value="propagated-error">Propagated error</option><option value="independent-errors">Independent errors</option><option value="service-dependency">Service dependency</option><option value="repeated-downstream">Repeated downstream</option>
        </select>
        <button className="rounded border border-forge-accent/60 px-3 py-1 text-forge-accent hover:bg-forge-base disabled:opacity-60" disabled={generating} onClick={generateTrace}>{generating ? "Generating…" : "Generate trace"}</button>
        {message && <span className="text-forge-highlight">{message}</span>}
      </div>
      {!traces.length ? <p className="rounded-md border border-forge-border p-4 text-forge-muted">{hasFilters ? "No traces match the current filters." : "No traces have been received yet."}</p> : (
        <div className="overflow-hidden rounded-md border border-forge-border">
          <div className="hidden grid-cols-[1.2fr_1fr_1fr_.7fr_.5fr_.6fr_.8fr_.9fr_.9fr_1.3fr] gap-3 bg-forge-panel px-3.5 py-3 text-xs uppercase tracking-wide text-forge-muted xl:grid"><span>Start</span><span>Root service</span><span>Root operation</span><span>Duration</span><span>Spans</span><span>Services</span><span>Findings</span><span>Completeness</span><span>Analysis</span><span>Trace ID</span></div>
          {traces.map((trace) => (
            <Link className="grid grid-cols-2 gap-3 border-t border-forge-border px-3.5 py-3 text-forge-text no-underline hover:bg-forge-base/70 xl:grid-cols-[1.2fr_1fr_1fr_.7fr_.5fr_.6fr_.8fr_.9fr_.9fr_1.3fr] xl:items-center" href={`/traces/${trace.trace_id}`} key={trace.trace_id}>
              <span>{formatTimestamp(trace.start_time_unix_ns)}</span><span>{trace.root_service?.name ?? "—"}</span><span>{trace.root_operation ?? "—"}</span><span>{formatDuration(trace.duration_ns)}</span><span>{trace.span_count}</span><span>{trace.service_count}</span><span>{trace.finding_count ? `${trace.finding_count} · ${trace.highest_finding_severity}` : "—"}</span>
              <span className="w-fit rounded-full border border-forge-highlight/70 px-2 py-0.5 text-xs text-forge-highlight">{trace.completeness_state}</span><span className="w-fit rounded-full border border-forge-accent/60 px-2 py-0.5 text-xs text-forge-accent">{trace.analysis_state ?? (trace.completeness_state === "PROCESSING" ? "NOT ELIGIBLE" : "NOT ANALYZED")}</span><code className="text-xs text-forge-accent">{trace.trace_id}</code>
            </Link>
          ))}
        </div>
      )}
      {nextHref && <Link className="mt-4 inline-block text-forge-accent hover:text-forge-text" href={nextHref}>Next</Link>}
    </>
  );
}
