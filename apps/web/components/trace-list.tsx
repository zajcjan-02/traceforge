"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import type { TraceSummary } from "../lib/api";
import { formatDuration, formatTimestamp } from "../lib/timing";

export function TraceList({ traces }: { traces: TraceSummary[] }) {
  const router = useRouter();
  const [newestFirst, setNewestFirst] = useState(true);
  const [scenario, setScenario] = useState("normal");
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState("");
  const sortedTraces = useMemo(() => [...traces].sort((left, right) => {
    const comparison = BigInt(left.start_time_unix_ns) < BigInt(right.start_time_unix_ns) ? -1 : BigInt(left.start_time_unix_ns) > BigInt(right.start_time_unix_ns) ? 1 : 0;
    return newestFirst ? -comparison : comparison;
  }), [newestFirst, traces]);

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

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-forge-border bg-forge-panel p-3 text-sm">
        <label className="text-forge-muted">Sort <select className="ml-1 rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" onChange={(event) => setNewestFirst(event.target.value === "newest")} value={newestFirst ? "newest" : "oldest"}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label>
        <span className="ml-auto text-forge-muted">Debug</span>
        <select aria-label="Debug trace scenario" className="rounded border border-forge-border bg-forge-base px-2 py-1 text-forge-text" onChange={(event) => setScenario(event.target.value)} value={scenario}>
          <option value="normal">Normal trace</option><option value="repeated-db">Repeated database</option><option value="critical-path">Critical path</option><option value="latency-contributor">Latency contributor</option><option value="propagated-error">Propagated error</option><option value="independent-errors">Independent errors</option><option value="service-dependency">Service dependency</option><option value="repeated-downstream">Repeated downstream</option>
        </select>
        <button className="rounded border border-forge-accent/60 px-3 py-1 text-forge-accent hover:bg-forge-base disabled:opacity-60" disabled={generating} onClick={generateTrace}>{generating ? "Generating…" : "Generate trace"}</button>
        {message && <span className="text-forge-highlight">{message}</span>}
      </div>
      {!traces.length ? <p className="rounded-md border border-forge-border p-4 text-forge-muted">No traces received yet.</p> : (
        <div className="overflow-hidden rounded-md border border-forge-border">
          <div className="hidden grid-cols-[1.7fr_.8fr_.5fr_.6fr_.9fr_.9fr_1.5fr] gap-3 bg-forge-panel px-3.5 py-3 text-xs uppercase tracking-wide text-forge-muted md:grid">
            <span>Start</span><span>Duration</span><span>Spans</span><span>Services</span><span>Completeness</span><span>Analysis</span><span>Trace ID</span>
          </div>
          {sortedTraces.map((trace) => (
            <Link className="grid grid-cols-2 gap-3 border-t border-forge-border px-3.5 py-3 text-forge-text no-underline hover:bg-forge-base/70 md:grid-cols-[1.7fr_.8fr_.5fr_.6fr_.9fr_.9fr_1.5fr] md:items-center" href={`/traces/${trace.trace_id}`} key={trace.trace_id}>
              <span>{formatTimestamp(trace.start_time_unix_ns)}</span>
              <span>{formatDuration(trace.duration_ns)}</span>
              <span>{trace.span_count}</span>
              <span>{trace.service_count}</span>
              <span className="w-fit rounded-full border border-forge-highlight/70 px-2 py-0.5 text-xs text-forge-highlight">{trace.completeness_state}</span>
              <span className="w-fit rounded-full border border-forge-accent/60 px-2 py-0.5 text-xs text-forge-accent">{trace.analysis_state ?? (trace.completeness_state === "PROCESSING" ? "NOT ELIGIBLE" : "NOT ANALYZED")}</span>
              <code className="text-xs text-forge-accent">{trace.trace_id}</code>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
