"use client";

import { useMemo, useState } from "react";

import type { Finding, JsonValue, Span, TraceDetail } from "../lib/api";
import { formatDuration, formatTimestamp, waterfallPosition } from "../lib/timing";

type Row = { span: Span; depth: number };

const label = "text-xs uppercase tracking-wide text-forge-muted";
const badge = "mt-1 w-fit rounded-full border px-2 py-0.5 text-xs";

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

function analysisMessage(detail: TraceDetail, findingCount: number) {
  const state = detail.analysis.state;
  if (state === null) return detail.trace.completeness_state === "PROCESSING" ? "Analysis becomes eligible after trace finalization." : "No analysis was scheduled for this trace.";
  if (state === "PENDING") return "Analysis is queued.";
  if (state === "RUNNING") return "Analysis is running.";
  if (state === "FAILED") return "Analysis failed. Raw telemetry remains available.";
  if (state === "PARTIAL") return findingCount ? "Analysis completed partially; available findings are shown below." : "Analysis completed partially; some detectors did not complete.";
  return "Analysis completed with no findings.";
}

function text(value: JsonValue | undefined) {
  return typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : "Unavailable";
}

function duration(value: JsonValue | undefined) {
  return typeof value === "string" ? formatDuration(value) : "Unavailable";
}

function percent(value: JsonValue | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return `${(value * 100).toFixed(1)}%`;
}

function primarySpanId(finding: Finding) {
  const key = finding.type === "MAJOR_LATENCY_CONTRIBUTOR" ? "span_id" : finding.type === "LIKELY_ERROR_ORIGIN" ? "origin_span_id" : null;
  const value = key ? finding.structured_data[key] : null;
  return typeof value === "string" ? value : null;
}

function chain(finding: Finding) {
  const evidence = finding.evidence.find((item) => item.type === "ERROR_PROPAGATION_CHAIN");
  const value = evidence?.structured_data.chain;
  return Array.isArray(value) ? value.filter((item): item is Record<string, JsonValue> => typeof item === "object" && item !== null && !Array.isArray(item)) : [];
}

function Evidence({ finding }: { finding: Finding }) {
  const data = finding.structured_data;
  if (finding.type === "MAJOR_LATENCY_CONTRIBUTOR") {
    return <EvidenceGrid items={[
      ["Service / span", `${text(data.service)} / ${text(data.span_name)}`],
      ["Critical-path contribution", duration(data.contribution_ns)],
      ["Critical-path duration", duration(data.critical_path_duration_ns)],
      ["Contribution", percent(data.contribution_fraction)],
      ["Canonical span duration", duration(data.canonical_duration_ns)],
    ]} />;
  }
  if (finding.type === "REPEATED_DATABASE_OPERATION") {
    return <EvidenceGrid items={[
      ["Service", text(data.service)], ["Operation", text(data.normalized_operation)], ["Count", text(data.count)],
      ["Sequential", text(data.sequential_count)], ["Combined duration", duration(data.combined_duration_ns)],
    ]} />;
  }
  if (finding.type === "LIKELY_ERROR_ORIGIN") {
    const propagation = chain(finding);
    return <div className="mt-3 grid gap-3 rounded border border-forge-border bg-forge-base/70 p-3 text-sm">
      <EvidenceGrid items={[
        ["Origin", `${text(data.service)} / ${text(data.span_name)}`], ["Error", `${text(data.error_source)} / ${text(data.error_type)}`],
        ["First observed", formatTimestamp(typeof data.first_error_timestamp_unix_ns === "string" ? data.first_error_timestamp_unix_ns : null)],
        ["Concrete exception", data.has_concrete_exception === true ? "Yes" : "No"],
      ]} />
      {propagation.length > 0 && <div><p className={label}>Propagation chain</p><ol className="mt-1 flex flex-wrap gap-2 font-mono text-xs text-forge-accent">{propagation.map((item) => <li key={text(item.span_id)}>{text(item.service)} / {text(item.span_name)}</li>)}</ol></div>}
    </div>;
  }
  if (finding.type === "REPEATED_DOWNSTREAM_OPERATION") {
    return <EvidenceGrid items={[
      ["Source", text(data.source_service)], ["Target", text(data.target_peer)], ["Protocol", text(data.protocol)],
      ["Operation", text(data.normalized_operation)], ["Count", text(data.count)], ["Sequential", text(data.sequential_count)],
      ["Combined duration", duration(data.combined_duration_ns)],
    ]} />;
  }
  return null;
}

function EvidenceGrid({ items }: { items: Array<[string, string]> }) {
  return <dl className="mt-3 grid gap-x-6 gap-y-2 rounded border border-forge-border bg-forge-base/70 p-3 text-sm sm:grid-cols-2">
    {items.map(([name, value]) => <div key={name}><dt className={label}>{name}</dt><dd className="mt-1 break-words">{value}</dd></div>)}
  </dl>;
}

function RawEvidence({ finding }: { finding: Finding }) {
  return <details className="mt-3">
    <summary className="cursor-pointer text-forge-muted">Raw evidence</summary>
    <pre className="mt-2 overflow-auto rounded bg-forge-base p-3 text-xs text-forge-muted">{JSON.stringify(finding.structured_data, null, 2)}</pre>
    {finding.evidence.map((item) => <pre className="mt-2 overflow-auto rounded bg-forge-base p-3 text-xs text-forge-muted" key={item.type}>{item.type}{"\n"}{JSON.stringify(item.structured_data, null, 2)}</pre>)}
  </details>;
}

export function TraceView({ detail, initialFindingId }: { detail: TraceDetail; initialFindingId?: string }) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(initialFindingId ?? null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const rows = useMemo(() => rowsFor(detail.spans), [detail.spans]);
  const findings = detail.analysis.current_run?.findings ?? [];
  const selectedFinding = findings.find((finding) => finding.finding_id === selectedFindingId);
  const relatedSpans = new Set(selectedFinding?.related_span_ids ?? []);
  const primarySpan = selectedFinding ? primarySpanId(selectedFinding) : null;
  const selectedSpan = detail.spans.find((span) => span.span_id === selectedSpanId);

  return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12">
    <a className="text-forge-muted no-underline hover:text-forge-text" href="/traces">← Traces</a>
    <header className="mt-5 grid gap-3.5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
      <div><h1 className="text-2xl font-semibold">Trace</h1><code className="text-xs text-forge-accent">{detail.trace.trace_id}</code></div>
      <dl className="m-0 flex flex-wrap gap-x-7 gap-y-4">
        <div><dt className={label}>Duration</dt><dd className="mt-1">{formatDuration(detail.trace.duration_ns)}</dd></div>
        <div><dt className={label}>Spans</dt><dd className="mt-1">{detail.trace.span_count}</dd></div>
        <div><dt className={label}>Revision</dt><dd className="mt-1">{detail.trace.revision}</dd></div>
        <div><dt className={label}>Completeness</dt><dd className={`${badge} border-forge-highlight/70 text-forge-highlight`}>{detail.trace.completeness_state}</dd></div>
        <div><dt className={label}>Analysis</dt><dd className={`${badge} border-forge-accent/60 text-forge-accent`}>{detail.analysis.state ?? (detail.trace.completeness_state === "PROCESSING" ? "NOT ELIGIBLE" : "NOT ANALYZED")}</dd></div>
      </dl>
      <p className="m-0 text-forge-muted">Services: {detail.trace.services.map((service) => service.name).join(", ") || "Unknown"}</p>
      {detail.trace.completeness_state === "INCOMPLETE" && <p className="m-0 rounded border border-forge-highlight/70 bg-forge-base/70 p-3 text-sm text-forge-highlight">This trace is incomplete. Findings remain available, but the observed execution may be missing telemetry.</p>}
    </header>

    <section className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
      <h2 className="mb-4 text-xl font-semibold">Findings</h2>
      {detail.analysis.state === "PARTIAL" && <p className="mb-3 rounded border border-forge-highlight/70 bg-forge-base/70 p-3 text-sm text-forge-highlight">Analysis is partial. Available findings are shown below.</p>}
      {!findings.length ? <p className="rounded-md border border-forge-border p-4 text-forge-muted">{analysisMessage(detail, findings.length)}</p> : findings.map((finding) => {
        const selected = finding.finding_id === selectedFindingId;
        const primary = primarySpanId(finding);
        return <article className={`border-t border-forge-border py-3.5 first:border-t-0 ${selected ? "selected -mx-2 rounded bg-forge-base/70 px-2" : ""}`} key={finding.finding_id}>
          <button aria-pressed={selected} className="w-full border-0 bg-transparent text-left text-forge-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-forge-accent" onClick={() => setSelectedFindingId(selected ? null : finding.finding_id)}>
            <span className="rounded-full border border-forge-highlight/70 px-2 py-0.5 text-xs text-forge-highlight">{finding.severity}</span>{" "}
            <span className="rounded-full border border-forge-accent/60 px-2 py-0.5 text-xs text-forge-accent">{finding.confidence}</span>
            <strong className="ml-2">{finding.title || finding.type}</strong>
          </button>
          <p>{finding.summary}</p>
          {finding.interpretation && <p className="text-forge-muted">{finding.interpretation}</p>}
          <Evidence finding={finding} />
          {primary && <p className="mt-3 text-sm text-forge-muted">Primary span: <code className="text-xs text-forge-accent">{primary}</code></p>}
          <p className="mt-3 text-sm">Related spans: {finding.related_span_ids.map((spanId) => <button className="mx-1 border-0 bg-transparent font-mono text-xs text-forge-accent underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-forge-accent" key={spanId} onClick={() => setSelectedSpanId(spanId)}>{spanId}</button>)}</p>
          <RawEvidence finding={finding} />
        </article>;
      })}
    </section>

    <section className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
      <h2 className="mb-4 text-xl font-semibold">Execution waterfall</h2>
      <div className="grid grid-cols-[minmax(150px,45%)_1fr] gap-3 px-2 pb-2 text-xs uppercase tracking-wide text-forge-muted md:grid-cols-[minmax(230px,32%)_100px_1fr]"><span>Operation</span><span>Duration</span><span className="hidden md:block">Timeline</span></div>
      {rows.map(({ span, depth }) => {
        const timing = waterfallPosition(detail.trace, span);
        const related = relatedSpans.has(span.span_id);
        const selected = selectedSpanId === span.span_id;
        const primary = primarySpan === span.span_id;
        const state = selected ? "selected-span border-forge-accent bg-forge-base/80" : primary ? "primary-span border-l-2 border-forge-accent bg-forge-base/70" : related ? "highlighted bg-forge-base/70" : "";
        return <button className={`grid w-full grid-cols-[minmax(150px,45%)_1fr] gap-3 border-0 border-t border-forge-border p-2 text-left text-forge-text hover:bg-forge-base/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-forge-accent md:grid-cols-[minmax(230px,32%)_100px_1fr] ${state}`} data-testid={`span-row-${span.span_id}`} key={span.span_id} onClick={() => setSelectedSpanId(span.span_id)}>
          <span className="span-label overflow-hidden text-ellipsis whitespace-nowrap" style={{ paddingLeft: `${depth * 18}px` }}><small className="block text-xs text-forge-muted">{span.service?.name ?? "unknown"}{primary ? " · primary" : ""}</small>{span.name}</span>
          <span>{formatDuration(span.duration_ns)}</span>
          <span className="relative col-span-2 h-[18px] overflow-hidden bg-forge-base md:col-span-1">{timing ? <i className={`timeline-bar absolute top-[3px] h-3 rounded-sm ${selected || primary ? "bg-forge-accent" : related ? "bg-forge-highlight" : "bg-forge-muted"}`} data-testid={`bar-${span.span_id}`} style={{ left: `${timing.left}%`, width: `${timing.width}%` }} /> : <em className="text-xs not-italic text-forge-muted">Timing unavailable</em>}</span>
        </button>;
      })}
    </section>

    {selectedSpan && <aside className="mt-5 rounded-md border border-forge-border bg-forge-panel p-[18px]">
      <h2 className="mb-4 text-xl font-semibold">Span inspector</h2>
      {relatedSpans.has(selectedSpan.span_id) && <p className="mb-3 rounded border border-forge-highlight/70 bg-forge-base/70 p-3 text-sm text-forge-highlight">Related to the selected finding{primarySpan === selectedSpan.span_id ? " (primary span)" : ""}.</p>}
      <dl className="m-0 flex flex-wrap gap-x-7 gap-y-4">
        <div><dt className={label}>Span ID</dt><dd className="mt-1"><code className="text-xs text-forge-accent">{selectedSpan.span_id}</code></dd></div>
        <div><dt className={label}>Parent ID</dt><dd className="mt-1"><code className="text-xs text-forge-accent">{selectedSpan.parent_span_id ?? "None"}</code></dd></div>
        <div><dt className={label}>Service</dt><dd className="mt-1">{selectedSpan.service?.name ?? "Unknown"}</dd></div>
        <div><dt className={label}>Name</dt><dd className="mt-1">{selectedSpan.name}</dd></div>
        <div><dt className={label}>Kind / status</dt><dd className="mt-1">{selectedSpan.span_kind} / {selectedSpan.status}</dd></div>
        <div><dt className={label}>Duration</dt><dd className="mt-1">{formatDuration(selectedSpan.duration_ns)}</dd></div>
        <div><dt className={label}>Start / end</dt><dd className="mt-1">{formatTimestamp(selectedSpan.start_time_unix_ns)} / {formatTimestamp(selectedSpan.end_time_unix_ns)}</dd></div>
      </dl>
      <details className="mt-3" open><summary className="cursor-pointer text-forge-muted">Attributes</summary><pre className="mt-2 overflow-auto rounded bg-forge-base p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.attributes, null, 2)}</pre></details>
      <details className="mt-3"><summary className="cursor-pointer text-forge-muted">Resource attributes</summary><pre className="mt-2 overflow-auto rounded bg-forge-base p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.resource_attributes, null, 2)}</pre></details>
      <details className="mt-3" open><summary className="cursor-pointer text-forge-muted">Events</summary><pre className="mt-2 overflow-auto rounded bg-forge-base p-3 text-xs text-forge-muted">{JSON.stringify(selectedSpan.events, null, 2)}</pre></details>
    </aside>}
  </section>;
}
