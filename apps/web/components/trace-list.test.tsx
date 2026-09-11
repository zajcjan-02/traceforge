import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import { TraceList } from "./trace-list";

const trace = {
  trace_id: "0123456789abcdef0123456789abcdef", revision: 2,
  start_time_unix_ns: "1788878620242827100", end_time_unix_ns: "1788878620242950100",
  duration_ns: "123000", span_count: 2, service_count: 1,
  completeness_state: "COMPLETE", analysis_state: "COMPLETE",
};

describe("TraceList", () => {
  it("renders metadata and links to detail", () => {
    render(<TraceList traces={[trace]} />);

    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getAllByText("COMPLETE")).toHaveLength(2);
    expect(screen.getByRole("link")).toHaveAttribute("href", `/traces/${trace.trace_id}`);
  });

  it("renders an empty state", () => {
    render(<TraceList traces={[]} />);

    expect(screen.getByText("No traces received yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate trace" })).toBeInTheDocument();
  });

  it("sorts traces by start time", () => {
    const older = { ...trace, trace_id: "older", start_time_unix_ns: "1" };
    const newer = { ...trace, trace_id: "newer", start_time_unix_ns: "2" };
    render(<TraceList traces={[older, newer]} />);

    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/traces/newer");
    fireEvent.change(screen.getByRole("combobox", { name: /sort/i }), { target: { value: "oldest" } });
    expect(screen.getAllByRole("link")[0]).toHaveAttribute("href", "/traces/older");
  });
});
