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
      root_service: null, root_operation: null, finding_count: 0, highest_finding_severity: null,
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
  it("selects a finding without inventing a span selection", () => {
    render(<TraceView detail={detail()} />);

    expect(screen.getByText("INCOMPLETE")).toBeInTheDocument();
    expect(screen.getByText("Repeated database operation")).toBeInTheDocument();
    expect(screen.getByTestId("span-row-child").querySelector(".span-label")).toHaveStyle({ paddingLeft: "18px" });
    expect(screen.getByTestId("bar-child")).toHaveStyle({ left: "20%", width: "50%" });
    expect(screen.getByTestId("bar-concurrent")).toHaveStyle({ left: "20%", width: "70%" });

    fireEvent.click(screen.getByText("Repeated database operation"));
    expect(screen.getByTestId("span-row-child")).toHaveClass("highlighted");
    expect(screen.getByTestId("span-row-concurrent")).toHaveClass("highlighted");
    expect(screen.queryByText("Span inspector")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "child" }));
    expect(screen.getByText("Span inspector")).toBeInTheDocument();
    expect(screen.getByText("Related to the selected finding.")).toBeInTheDocument();
    expect(screen.getByText(/"name": "exception"/)).toBeInTheDocument();
    expect(screen.getByText(/"exception.type": "Timeout"/)).toBeInTheDocument();
  });

  it("selects a current deep-linked finding and ignores unknown finding IDs", () => {
    const { unmount } = render(<TraceView detail={detail()} initialFindingId="finding" />);
    expect(screen.getByTestId("span-row-child")).toHaveClass("highlighted");
    expect(screen.getByTestId("span-row-concurrent")).toHaveClass("highlighted");

    unmount();
    render(<TraceView detail={detail()} initialFindingId="stale-finding" />);
    expect(screen.getByTestId("span-row-child")).not.toHaveClass("highlighted");
    expect(screen.getByTestId("span-row-concurrent")).not.toHaveClass("highlighted");
  });

  it("renders detector-specific evidence and keeps unknown findings usable", () => {
    const value = detail();
    value.analysis.current_run!.findings = [
      {
        finding_id: "latency", type: "MAJOR_LATENCY_CONTRIBUTOR", severity: "HIGH", confidence: "HIGH",
        title: "Major latency contributor", summary: "Slow payment.", observation: null, interpretation: null,
        structured_data: { span_id: "child", service: "orders", span_name: "database query", contribution_ns: "500", critical_path_duration_ns: "1000", contribution_fraction: 0.5, canonical_duration_ns: "900" }, related_span_ids: ["child"], evidence: [],
      },
      {
        finding_id: "database", type: "REPEATED_DATABASE_OPERATION", severity: "MEDIUM", confidence: "HIGH",
        title: "Repeated database operation", summary: "Repeated query.", observation: null, interpretation: null,
        structured_data: { service: "orders", normalized_operation: "SELECT product", count: 5, sequential_count: 4, combined_duration_ns: "500" }, related_span_ids: ["child"], evidence: [],
      },
      {
        finding_id: "origin", type: "LIKELY_ERROR_ORIGIN", severity: "HIGH", confidence: "HIGH",
        title: "Likely error origin", summary: "Payment failed.", observation: null, interpretation: null,
        structured_data: { origin_span_id: "child", service: "orders", span_name: "database query", error_source: "exception_event", error_type: "Timeout", first_error_timestamp_unix_ns: "9007199254740993600", has_concrete_exception: true }, related_span_ids: ["child", "root"],
        evidence: [{ type: "ERROR_PROPAGATION_CHAIN", description: null, structured_data: { chain: [{ span_id: "child", service: "orders", span_name: "database query" }, { span_id: "root", service: "gateway", span_name: "request" }] } }],
      },
      {
        finding_id: "downstream", type: "REPEATED_DOWNSTREAM_OPERATION", severity: "LOW", confidence: "MEDIUM",
        title: "Repeated downstream operation", summary: "Repeated downstream call.", observation: null, interpretation: null,
        structured_data: { source_service: "orders", target_peer: "inventory", protocol: "HTTP", normalized_operation: "GET /products/{id}", count: 5, sequential_count: 1, combined_duration_ns: "700" }, related_span_ids: ["concurrent"], evidence: [],
      },
      {
        finding_id: "unknown", type: "FUTURE_FINDING", severity: "LOW", confidence: "LOW",
        title: "Future finding", summary: "Unknown evidence remains visible.", observation: null, interpretation: null,
        structured_data: { future_field: "value" }, related_span_ids: [], evidence: [],
      },
    ];
    render(<TraceView detail={value} />);

    expect(screen.getByText("Critical-path contribution")).toBeInTheDocument();
    expect(screen.getByText("50.0%")).toBeInTheDocument();
    expect(screen.getByText("SELECT product")).toBeInTheDocument();
    expect(screen.getByText("Propagation chain")).toBeInTheDocument();
    expect(screen.getByText("GET /products/{id}")).toBeInTheDocument();
    fireEvent.click(screen.getAllByText("Raw evidence", { exact: true })[4]);
    expect(screen.getByText(/"future_field": "value"/)).toBeInTheDocument();
  });

  it("does not confuse pending analysis with no findings", () => {
    render(<TraceView detail={detail("PENDING")} />);

    expect(screen.getByText("Analysis is queued.")).toBeInTheDocument();
  });

  it("distinguishes processing eligibility from finalized legacy traces", () => {
    const processing = detail(null);
    processing.trace.completeness_state = "PROCESSING";
    render(<TraceView detail={processing} />);
    expect(screen.getByText("NOT ELIGIBLE")).toBeInTheDocument();
    expect(screen.getByText("Analysis becomes eligible after trace finalization.")).toBeInTheDocument();

    const legacy = detail(null);
    legacy.trace.completeness_state = "COMPLETE";
    render(<TraceView detail={legacy} />);
    expect(screen.getByText("NOT ANALYZED")).toBeInTheDocument();
    expect(screen.getByText("No analysis was scheduled for this trace.")).toBeInTheDocument();
  });

  it("makes failed analysis explicit", () => {
    render(<TraceView detail={detail("FAILED")} />);

    expect(screen.getByText("Analysis failed. Raw telemetry remains available.")).toBeInTheDocument();
  });

  it("shows partial analysis and incomplete telemetry without hiding findings", () => {
    const value = detail("PARTIAL");
    value.analysis.current_run = { analysis_run_id: "run", trace_revision: 2, state: "PARTIAL", detector_results: [], findings: detail().analysis.current_run!.findings };
    render(<TraceView detail={value} />);

    expect(screen.getAllByText(/This trace is incomplete/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Analysis is partial/)).toBeInTheDocument();
    expect(screen.getByText("Repeated database operation")).toBeInTheDocument();
  });
});
