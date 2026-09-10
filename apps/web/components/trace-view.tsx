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
    <details>
      <summary>Evidence</summary>
      <pre>{JSON.stringify(finding.structured_data, null, 2)}</pre>
      {finding.evidence.map((evidence) => <pre key={evidence.type}>{evidence.type}{"\n"}{JSON.stringify(evidence.structured_data, null, 2)}</pre>)}
    </details>
  );
}

export function TraceView({ detail }: { detail: TraceDetail }) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const rows = useMemo(() => rowsFor(detail.spans), [detail.spans]);
  const selectedFinding = detail.analysis.current_run?.findings.find((finding) => finding.finding_id === selectedFindingId);
  const highlighted = new Set(selectedFinding?.related_span_ids ?? []);
  const selectedSpan = detail.spans.find((span) => span.span_id === selectedSpanId);
  const findings = detail.analysis.current_run?.findings ?? [];

  return (
    <section className="page trace-page">
      <a className="back-link" href="/traces">← Traces</a>
      <header className="trace-overview">
        <div><h1>Trace</h1><code>{detail.trace.trace_id}</code></div>
        <dl>
          <div><dt>Duration</dt><dd>{formatDuration(detail.trace.duration_ns)}</dd></div>
          <div><dt>Spans</dt><dd>{detail.trace.span_count}</dd></div>
          <div><dt>Revision</dt><dd>{detail.trace.revision}</dd></div>
          <div><dt>Completeness</dt><dd className={`badge ${detail.trace.completeness_state.toLowerCase()}`}>{detail.trace.completeness_state}</dd></div>
          <div><dt>Analysis</dt><dd className="badge">{detail.analysis.state ?? "NOT ELIGIBLE"}</dd></div>
        </dl>
        <p className="services">Services: {detail.trace.services.map((service) => service.name).join(", ") || "Unknown"}</p>
      </header>

      <section className="findings-panel">
        <h2>Findings</h2>
        {!findings.length ? <p className="page-state">{analysisMessage(detail)}</p> : findings.map((finding) => (
          <article className={`finding ${finding.finding_id === selectedFindingId ? "selected" : ""}`} key={finding.finding_id}>
            <button onClick={() => {
              setSelectedFindingId(finding.finding_id);
              setSelectedSpanId(finding.related_span_ids[0] ?? null);
            }}>
              <span className="badge">{finding.severity}</span> <span className="badge">{finding.confidence}</span>
              <strong>{finding.title || finding.type}</strong>
            </button>
            <p>{finding.summary}</p>
            {finding.interpretation && <p className="interpretation">{finding.interpretation}</p>}
            <p className="related-spans">Related spans: {finding.related_span_ids.map((spanId) => (
              <button key={spanId} onClick={() => setSelectedSpanId(spanId)}>{spanId}</button>
            ))}</p>
            <Evidence finding={finding} />
          </article>
        ))}
      </section>

      <section className="waterfall-panel">
        <h2>Execution waterfall</h2>
        <div className="waterfall-heading"><span>Operation</span><span>Duration</span><span>Timeline</span></div>
        {rows.map(({ span, depth }) => {
          const timing = waterfallPosition(detail.trace, span);
          const isHighlighted = highlighted.has(span.span_id);
          return (
            <button
              className={`waterfall-row ${isHighlighted ? "highlighted" : ""}`}
              data-testid={`span-row-${span.span_id}`}
              key={span.span_id}
              onClick={() => setSelectedSpanId(span.span_id)}
            >
              <span className="span-label" style={{ paddingLeft: `${depth * 18}px` }}>
                <small>{span.service?.name ?? "unknown"}</small>{span.name}
              </span>
              <span>{formatDuration(span.duration_ns)}</span>
              <span className="timeline">
                {timing ? <i className="timeline-bar" data-testid={`bar-${span.span_id}`} style={{ left: `${timing.left}%`, width: `${timing.width}%` }} /> : <em>Timing unavailable</em>}
              </span>
            </button>
          );
        })}
      </section>

      {selectedSpan && <aside className="span-inspector">
        <h2>Span inspector</h2>
        <dl>
          <div><dt>Span ID</dt><dd><code>{selectedSpan.span_id}</code></dd></div>
          <div><dt>Parent ID</dt><dd><code>{selectedSpan.parent_span_id ?? "None"}</code></dd></div>
          <div><dt>Service</dt><dd>{selectedSpan.service?.name ?? "Unknown"}</dd></div>
          <div><dt>Name</dt><dd>{selectedSpan.name}</dd></div>
          <div><dt>Kind / status</dt><dd>{selectedSpan.span_kind} / {selectedSpan.status}</dd></div>
          <div><dt>Duration</dt><dd>{formatDuration(selectedSpan.duration_ns)}</dd></div>
          <div><dt>Start / end</dt><dd>{formatTimestamp(selectedSpan.start_time_unix_ns)} / {formatTimestamp(selectedSpan.end_time_unix_ns)}</dd></div>
        </dl>
        <details open><summary>Attributes</summary><pre>{JSON.stringify(selectedSpan.attributes, null, 2)}</pre></details>
        <details><summary>Resource attributes</summary><pre>{JSON.stringify(selectedSpan.resource_attributes, null, 2)}</pre></details>
        <details open><summary>Events</summary><pre>{JSON.stringify(selectedSpan.events, null, 2)}</pre></details>
      </aside>}
    </section>
  );
}
