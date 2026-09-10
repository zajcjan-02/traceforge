import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TraceDetail } from "../lib/api";
import { TraceView } from "./trace-view";

function detail(analysisState: string | null = "COMPLETE"): TraceDetail {
  return {
    trace: {
      trace_id: "0123456789abcdef0123456789abcdef", revision: 2,
      start_time_unix_ns: "9007199254740993000", end_time_unix_ns: "9007199254740994000",
      duration_ns: "1000", span_count: 3, service_count: 1,
      completeness_state: "INCOMPLETE", analysis_state: analysisState,
      last_received_at: "2026-09-10T00:00:00Z", services: [{ service_id: 1, name: "orders", namespace: "" }],
    },
    analysis: {
      state: analysisState,
      current_run: analysisState === "COMPLETE" ? {
        analysis_run_id: "run", trace_revision: 2, state: "COMPLETE", detector_results: [],
        findings: [{
          finding_id: "finding", type: "REPEATED_DATABASE_OPERATION", severity: "MEDIUM", confidence: "HIGH",
          title: "Repeated database operation", summary: "Five repeated operations.",
          observation: "Five operations were observed.", interpretation: "This may indicate redundant access.",
          structured_data: { count: 5, combined_duration_ns: "500" }, related_span_ids: ["child", "concurrent"],
          evidence: [{ type: "OPERATION_COUNT", description: null, structured_data: { count: 5 } }],
        }],
      } : null,
    },
    spans: [
      {
        span_id: "root", parent_span_id: null, service: { name: "orders", namespace: "" }, name: "request",
        span_kind: "SERVER", start_time_unix_ns: "9007199254740993000", end_time_unix_ns: "9007199254740994000",
        duration_ns: "1000", status: "UNSET", attributes: {}, resource_attributes: {}, events: [],
      },
      {
        span_id: "child", parent_span_id: "root", service: { name: "orders", namespace: "" }, name: "database query",
        span_kind: "CLIENT", start_time_unix_ns: "9007199254740993200", end_time_unix_ns: "9007199254740993700",
        duration_ns: "500", status: "ERROR", attributes: { "db.system.name": "postgresql" }, resource_attributes: {},
        events: [{ event_index: 0, name: "exception", timestamp_unix_ns: "9007199254740993600", attributes: { "exception.type": "Timeout" } }],
      },
      {
        span_id: "concurrent", parent_span_id: "root", service: { name: "orders", namespace: "" }, name: "remote call",
        span_kind: "CLIENT", start_time_unix_ns: "9007199254740993200", end_time_unix_ns: "9007199254740993900",
        duration_ns: "700", status: "UNSET", attributes: {}, resource_attributes: {}, events: [],
      },
    ],
  };
}

describe("TraceView", () => {
  it("renders hierarchy, concurrent timing, findings, and inspector data", () => {
    render(<TraceView detail={detail()} />);

    expect(screen.getByText("INCOMPLETE")).toBeInTheDocument();
    expect(screen.getByText("Repeated database operation")).toBeInTheDocument();
    expect(screen.getByTestId("span-row-child").querySelector(".span-label")).toHaveStyle({ paddingLeft: "18px" });
    expect(screen.getByTestId("bar-child")).toHaveStyle({ left: "20%", width: "50%" });
    expect(screen.getByTestId("bar-concurrent")).toHaveStyle({ left: "20%", width: "70%" });

    fireEvent.click(screen.getByText("Repeated database operation"));
    expect(screen.getByTestId("span-row-child")).toHaveClass("highlighted");
    expect(screen.getByTestId("span-row-concurrent")).toHaveClass("highlighted");
    expect(screen.getByText("Span inspector")).toBeInTheDocument();
    expect(screen.getByText(/"name": "exception"/)).toBeInTheDocument();
    expect(screen.getByText(/"exception.type": "Timeout"/)).toBeInTheDocument();
  });

  it("does not confuse pending analysis with no findings", () => {
    render(<TraceView detail={detail("PENDING")} />);

    expect(screen.getByText("Analysis is queued.")).toBeInTheDocument();
  });

  it("makes failed analysis explicit", () => {
    render(<TraceView detail={detail("FAILED")} />);

    expect(screen.getByText("Analysis failed. Raw telemetry remains available.")).toBeInTheDocument();
  });
});
