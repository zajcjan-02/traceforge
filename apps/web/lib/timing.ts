import type { Span, TraceSummary } from "./api";

export function formatDuration(value: string | null) {
  if (value === null) return "Unavailable";
  try {
    const duration = BigInt(value);
    if (duration < 1_000n) return `${duration} ns`;
    if (duration < 1_000_000n) return `${Number(duration) / 1_000} µs`;
    if (duration < 1_000_000_000n) return `${Number(duration) / 1_000_000} ms`;
    return `${(Number(duration) / 1_000_000_000).toFixed(2)} s`;
  } catch {
    return "Unavailable";
  }
}

export function formatTimestamp(value: string | null) {
  if (value === null) return "Unavailable";
  try {
    return new Date(Number(BigInt(value) / 1_000_000n)).toISOString();
  } catch {
    return value;
  }
}

export function waterfallPosition(trace: TraceSummary, span: Span) {
  if (trace.duration_ns === null || span.end_time_unix_ns === null) return null;
  try {
    const duration = BigInt(trace.duration_ns);
    const traceStart = BigInt(trace.start_time_unix_ns);
    const start = BigInt(span.start_time_unix_ns);
    const end = BigInt(span.end_time_unix_ns);
    if (duration <= 0n || end < start) return null;
    const clampedStart = start < traceStart ? traceStart : start;
    const traceEnd = traceStart + duration;
    const clampedEnd = end > traceEnd ? traceEnd : end;
    if (clampedStart >= traceEnd || clampedEnd <= clampedStart) return null;
    const left = clampedStart - traceStart;
    const width = clampedEnd - clampedStart;
    return {
      left: Number((left * 10_000n) / duration) / 100,
      width: Number((width * 10_000n) / duration) / 100,
    };
  } catch {
    return null;
  }
}
