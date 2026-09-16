import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));

import { TraceList } from "./trace-list";

const trace = {
  trace_id: "0123456789abcdef0123456789abcdef", revision: 2,
  start_time_unix_ns: "1788878620242827100", end_time_unix_ns: "1788878620242950100",
  duration_ns: "123000", span_count: 2, service_count: 1,
  completeness_state: "COMPLETE", analysis_state: "COMPLETE",
  root_service: { service_id: 1, name: "orders", namespace: "" },
  root_operation: "GET /orders", finding_count: 2, highest_finding_severity: "HIGH",
};

const service = { service_id: 1, name: "orders", namespace: "", first_seen_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:00:00Z" };

function renderList(options: Partial<Parameters<typeof TraceList>[0]> = {}) {
  return render(<TraceList filters={{}} nextHref={null} services={[service]} traces={[trace]} {...options} />);
}

describe("TraceList", () => {
  beforeEach(() => router.push.mockReset());

  it("renders enriched summary metadata and detail links", () => {
    renderList();

    expect(screen.getByText("GET /orders")).toBeInTheDocument();
    expect(screen.getByText("2 · HIGH")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /0123456789abcdef/ })).toHaveAttribute("href", `/traces/${trace.trace_id}`);
  });

  it("distinguishes empty data from a filtered empty result", () => {
    const { unmount } = renderList({ traces: [] });
    expect(screen.getByText("No traces have been received yet.")).toBeInTheDocument();

    unmount();
    renderList({ filters: { has_findings: "true" }, traces: [] });
    expect(screen.getByText("No traces match the current filters.")).toBeInTheDocument();
  });

  it("uses URL filters, BigInt duration conversion, and resets pagination", () => {
    renderList({ filters: { cursor: "old-cursor" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Service" }), { target: { value: "1" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Minimum duration" }), { target: { value: "2" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Minimum duration unit" }), { target: { value: "ms" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Has findings" }), { target: { value: "true" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Finding type" }), { target: { value: "LIKELY_ERROR_ORIGIN" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    expect(router.push).toHaveBeenCalledWith("/traces?service_id=1&has_findings=true&finding_type=LIKELY_ERROR_ORIGIN&order=received_desc&min_duration_ns=2000000");
  });

  it("preserves filters in the next-page link and clears them", () => {
    renderList({ filters: { service_id: "1", has_findings: "true" }, nextHref: "/traces?service_id=1&has_findings=true&cursor=opaque" });

    expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute("href", "/traces?service_id=1&has_findings=true&cursor=opaque");
    expect(screen.getByRole("link", { name: "Clear filters" })).toHaveAttribute("href", "/traces");
  });
});
