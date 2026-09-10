import Link from "next/link";

import type { TraceSummary } from "../lib/api";
import { formatDuration, formatTimestamp } from "../lib/timing";

export function TraceList({ traces }: { traces: TraceSummary[] }) {
  if (!traces.length) return <p className="page-state">No traces received yet.</p>;

  return (
    <div className="trace-table">
      <div className="trace-row trace-heading">
        <span>Start</span><span>Duration</span><span>Spans</span><span>Services</span><span>Completeness</span><span>Analysis</span><span>Trace ID</span>
      </div>
      {traces.map((trace) => (
        <Link className="trace-row" href={`/traces/${trace.trace_id}`} key={trace.trace_id}>
          <span>{formatTimestamp(trace.start_time_unix_ns)}</span>
          <span>{formatDuration(trace.duration_ns)}</span>
          <span>{trace.span_count}</span>
          <span>{trace.service_count}</span>
          <span className={`badge ${trace.completeness_state.toLowerCase()}`}>{trace.completeness_state}</span>
          <span className="badge">{trace.analysis_state ?? "NOT ELIGIBLE"}</span>
          <code>{trace.trace_id}</code>
        </Link>
      ))}
    </div>
  );
}
