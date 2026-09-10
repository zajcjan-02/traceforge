import { describe, expect, it } from "vitest";

import type { Span, TraceSummary } from "./api";
import { waterfallPosition } from "./timing";

const trace: TraceSummary = {
  trace_id: "trace", revision: 1, start_time_unix_ns: "9007199254740993000",
  end_time_unix_ns: "9007199254740994000", duration_ns: "1000", span_count: 1,
  service_count: 1, completeness_state: "COMPLETE", analysis_state: "COMPLETE",
};

function span(start: string, end: string | null): Span {
  return {
    span_id: "span", parent_span_id: null, service: null, name: "work", span_kind: "INTERNAL",
    start_time_unix_ns: start, end_time_unix_ns: end, duration_ns: end ? "100" : null,
    status: "UNSET", attributes: {}, resource_attributes: {}, events: [],
  };
}

describe("waterfallPosition", () => {
  it("uses exact BigInt arithmetic for unsafe nanoseconds", () => {
    expect(waterfallPosition(trace, span("9007199254740993200", "9007199254740993700"))).toEqual({ left: 20, width: 50 });
  });

  it("clamps presentation without changing canonical timestamps", () => {
    const value = span("9007199254740992900", "9007199254740994100");

    expect(waterfallPosition(trace, value)).toEqual({ left: 0, width: 100 });
    expect(value.start_time_unix_ns).toBe("9007199254740992900");
  });

  it("returns unavailable for invalid timing", () => {
    expect(waterfallPosition(trace, span("9007199254740993700", "9007199254740993200"))).toBeNull();
    expect(waterfallPosition({ ...trace, duration_ns: "0" }, span("9007199254740993200", "9007199254740993700"))).toBeNull();
  });
});
