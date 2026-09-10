import Link from "next/link";

import type { TraceSummary } from "../lib/api";
import { formatDuration, formatTimestamp } from "../lib/timing";

export function TraceList({ traces }: { traces: TraceSummary[] }) {
  if (!traces.length) return <p className="rounded-md border border-forge-border p-4 text-forge-muted">No traces received yet.</p>;

  return (
    <div className="overflow-hidden rounded-md border border-forge-border">
      <div className="hidden grid-cols-[1.7fr_.8fr_.5fr_.6fr_.9fr_.9fr_1.5fr] gap-3 bg-forge-panel px-3.5 py-3 text-xs uppercase tracking-wide text-forge-muted md:grid">
        <span>Start</span><span>Duration</span><span>Spans</span><span>Services</span><span>Completeness</span><span>Analysis</span><span>Trace ID</span>
      </div>
      {traces.map((trace) => (
        <Link className="grid grid-cols-2 gap-3 border-t border-forge-border px-3.5 py-3 text-forge-text no-underline hover:bg-white/10 md:grid-cols-[1.7fr_.8fr_.5fr_.6fr_.9fr_.9fr_1.5fr] md:items-center" href={`/traces/${trace.trace_id}`} key={trace.trace_id}>
          <span>{formatTimestamp(trace.start_time_unix_ns)}</span>
          <span>{formatDuration(trace.duration_ns)}</span>
          <span>{trace.span_count}</span>
          <span>{trace.service_count}</span>
          <span className="w-fit rounded-full border border-emerald-200/60 px-2 py-0.5 text-xs text-emerald-100">{trace.completeness_state}</span>
          <span className="w-fit rounded-full border border-forge-accent/60 px-2 py-0.5 text-xs text-forge-accent">{trace.analysis_state ?? "NOT ELIGIBLE"}</span>
          <code className="text-xs text-forge-accent">{trace.trace_id}</code>
        </Link>
      ))}
    </div>
  );
}
