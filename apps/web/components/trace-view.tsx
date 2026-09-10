"use client";

import { useMemo, useState } from "react";

import type { Finding, Span, TraceDetail } from "../lib/api";
import { formatDuration, formatTimestamp, waterfallPosition } from "../lib/timing";

type Row = { span: Span; depth: number };

function rowsFor(spans: Span[]) {
  const byId = new Map(spans.map((span) => [span.span_id, span]));
  const children = new Map<string, Span[]>();
  const roots: Span[] = [];
  for (const span of spans) {
    if (span.parent_span_id && byId.has(span.parent_span_id)) {
      children.set(span.parent_span_id, [...(children.get(span.parent_span_id) ?? []), span]);
    } else {
      roots.push(span);
    }
  }
  const compare = (left: Span, right: Span) => {
    try {
      const leftStart = BigInt(left.start_time_unix_ns);
      const rightStart = BigInt(right.start_time_unix_ns);
      if (leftStart !== rightStart) return leftStart < rightStart ? -1 : 1;
    } catch {
      return left.span_id.localeCompare(right.span_id);
    }
    return left.span_id.localeCompare(right.span_id);
  };
  const rows: Row[] = [];
  const add = (span: Span, depth: number) => {
    rows.push({ span, depth });
    (children.get(span.span_id) ?? []).sort(compare).forEach((child) => add(child, depth + 1));
  };
  roots.sort(compare).forEach((span) => add(span, 0));
  return rows;
}

function analysisMessage(detail: TraceDetail) {
  const state = detail.analysis.state;
  if (state === null) return "Analysis is not eligible until trace finalization.";
  if (state === "PENDING") return "Analysis is queued.";
  if (state === "RUNNING") return "Analysis is running.";
  if (state === "FAILED") return "Analysis failed. Raw telemetry remains available.";
  if (state === "PARTIAL") return "Analysis completed partially; inspect detector results.";
  return "Analysis completed with no findings.";
}

function Evidence({ finding }: { finding: Finding }) {
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-forge-muted">Evidence</summary>
      <pre className="mt-2 overflow-auto rounded bg-black/20 p-3 text-xs text-forge-muted">{JSON.stringify(finding.structured_data, null, 2)}</pre>
      {finding.evidence.map((evidence) => (
        <pre className="mt-2 overflow-auto rounded bg-black/20 p-3 text-xs text-forge-muted" key={evidence.type}>
          {evidence.type}{"\n"}{JSON.stringify(evidence.structured_data, null, 2)}
        </pre>
      ))}
    </details>
  );
}

const label = "text-xs uppercase tracking-wide text-forge-muted";
const badge = "mt-1 w-fit rounded-full border px-2 py-0.5 text-xs";

export function TraceView({ detail }: { detail: TraceDetail }) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const rows = useMemo(() => rowsFor(detail.spans), [detail.spans]);
  const selectedFinding = detail.analysis.current_run?.findings.find((finding) => finding.finding_id === selectedFindingId);
  const highlighted = new Set(selectedFinding?.related_span_ids ?? []);
  const selectedSpan = detail.spans.find((span) => span.span_id === selectedSpanId);
  const findings = detail.analysis.current_run?.findings ?? [];

  return (
    <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12">
      <a className="text-forge-muted no-underline hover:text-forge-text" href="/traces">← Traces</a>
      <header className="mt-5 grid gap-3.5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
        <div><h1 className="text-2xl font-semibold">Trace</h1><code className="text-xs text-forge-accent">{detail.trace.trace_id}</code></div>
        <dl className="m-0 flex flex-wrap gap-x-7 gap-y-4">
          <div><dt className={label}>Duration</dt><dd className="mt-1">{formatDuration(detail.trace.duration_ns)}</dd></div>
          <div><dt className={label}>Spans</dt><dd className="mt-1">{detail.trace.span_count}</dd></div>
          <div><dt className={label}>Revision</dt><dd className="mt-1">{detail.trace.revision}</dd></div>
          <div><dt className={label}>Completeness</dt><dd className={`${badge} border-emerald-200/60 text-emerald-100`}>{detail.trace.completeness_state}</dd></div>
          <div><dt className={label}>Analysis</dt><dd className={`${badge} border-forge-accent/60 text-forge-accent`}>{detail.analysis.state ?? "NOT ELIGIBLE"}</dd></div>
        </dl>
        <p className="m-0 text-forge-muted">Services: {detail.trace.services.map((service) => service.name).join(", ") || "Unknown"}</p>
      </header>

      <section className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
        <h2 className="mb-4 text-xl font-semibold">Findings</h2>
        {!findings.length ? <p className="rounded-md border border-forge-border p-4 text-forge-muted">{analysisMessage(detail)}</p> : findings.map((finding) => (
          <article className={`border-t border-forge-border py-3.5 first:border-t-0 ${finding.finding_id === selectedFindingId ? "selected -mx-2 bg-white/10 px-2" : ""}`} key={finding.finding_id}>
            <button className="border-0 bg-transparent text-left text-forge-text" onClick={() => {
              setSelectedFindingId(finding.finding_id);
              setSelectedSpanId(finding.related_span_ids[0] ?? null);
            }}>
              <span className="rounded-full border border-forge-highlight/70 px-2 py-0.5 text-xs text-forge-highlight">{finding.severity}</span>{" "}
              <span className="rounded-full border border-forge-accent/60 px-2 py-0.5 text-xs text-forge-accent">{finding.confidence}</span>
              <strong className="ml-2">{finding.title || finding.type}</strong>
            </button>
            <p>{finding.summary}</p>
            {finding.interpretation && <p className="text-forge-muted">{finding.interpretation}</p>}
            <p>Related spans: {finding.related_span_ids.map((spanId) => (
              <button className="mx-1 border-0 bg-transparent font-mono text-xs text-forge-accent" key={spanId} onClick={() => setSelectedSpanId(spanId)}>{spanId}</button>
            ))}</p>
            <Evidence finding={finding} />
          </article>
        ))}
      </section>

      <section className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
        <h2 className="mb-4 text-xl font-semibold">Execution waterfall</h2>
        <div className="grid grid-cols-[minmax(150px,45%)_1fr] gap-3 px-2 pb-2 text-xs uppercase tracking-wide text-forge-muted md:grid-cols-[minmax(230px,32%)_100px_1fr]"><span>Operation</span><span>Duration</span><span className="hidden md:block">Timeline</span></div>
        {rows.map(({ span, depth }) => {
          const timing = waterfallPosition(detail.trace, span);
          const isHighlighted = highlighted.has(span.span_id);
          return (
            <button
              className={`grid w-full grid-cols-[minmax(150px,45%)_1fr] gap-3 border-0 border-t border-forge-border bg-transparent p-2 text-left text-forge-text hover:bg-white/10 md:grid-cols-[minmax(230px,32%)_100px_1fr] ${isHighlighted ? "highlighted bg-white/10" : ""}`}
              data-testid={`span-row-${span.span_id}`}
              key={span.span_id}
              onClick={() => setSelectedSpanId(span.span_id)}
            >
              <span className="span-label overflow-hidden text-ellipsis whitespace-nowrap" style={{ paddingLeft: `${depth * 18}px` }}>
                <small className="block text-xs text-forge-muted">{span.service?.name ?? "unknown"}</small>{span.name}
              </span>
              <span>{formatDuration(span.duration_ns)}</span>
              <span className="relative col-span-2 h-[18px] overflow-hidden bg-black/20 md:col-span-1">
                {timing ? <i className={`timeline-bar absolute top-[3px] h-3 rounded-sm ${isHighlighted ? "bg-forge-highlight" : "bg-forge-accent"}`} data-testid={`bar-${span.span_id}`} style={{ left: `${timing.left}%`, width: `${timing.width}%` }} /> : <em className="text-xs not-italic text-forge-muted">Timing unavailable</em>}
              </span>
            </button>
          );
        })}
      </section>

      {selectedSpan && <aside className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
        <h2 className="mb-4 text-xl font-semibold">Span inspector</h2>
        <dl className="m-0 flex flex-wrap gap-x-7 gap-y-4">
          <div><dt className={label}>Span ID</dt><dd className="mt-1"><code className="text-xs text-forge-accent">{selectedSpan.span_id}</code></dd></div>
          <div><dt className={label}>Parent ID</dt><dd className="mt-1"><code className="text-xs text-forge-accent">{selectedSpan.parent_span_id ?? "None"}</code></dd></div>
          <div><dt className={label}>Service</dt><dd className="mt-1">{selectedSpan.service?.name ?? "Unknown"}</dd></div>
          <div><dt className={label}>Name</dt><dd className="mt-1">{selectedSpan.name}</dd></div>
          <div><dt className={label}>Kind / status</dt><dd className="mt-1">{selectedSpan.span_kind} / {selectedSpan.status}</dd></div>
          <div><dt className={label}>Duration</dt><dd className="mt-1">{formatDuration(selectedSpan.duration_ns)}</dd></div>
          <div><dt className={label}>Start / end</dt><dd className="mt-1">{formatTimestamp(selectedSpan.start_time_unix_ns)} / {formatTimestamp(selectedSpan.end_time_unix_ns)}</dd></div>
        </dl>
        <details className="mt-3" open><summary className="cursor-pointer text-forge-muted">Attributes</summary><pre className="mt-2 overflow-auto rounded bg-black/20 p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.attributes, null, 2)}</pre></details>
        <details className="mt-3"><summary className="cursor-pointer text-forge-muted">Resource attributes</summary><pre className="mt-2 overflow-auto rounded bg-black/20 p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.resource_attributes, null, 2)}</pre></details>
        <details className="mt-3" open><summary className="cursor-pointer text-forge-muted">Events</summary><pre className="mt-2 overflow-auto rounded bg-black/20 p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.events, null, 2)}</pre></details>
      </aside>}
    </section>
  );
}
