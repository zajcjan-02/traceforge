import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getRetentionStatus, getSystemHealth } = vi.hoisted(() => ({ getRetentionStatus: vi.fn(), getSystemHealth: vi.fn() }));

vi.mock("../../lib/api", () => ({ getRetentionStatus, getSystemHealth }));
vi.mock("../../components/retention-panel", () => ({ RetentionPanel: ({ retention }: { retention: { eligible_trace_count: number } }) => <div>Retention eligible: {retention.eligible_trace_count}</div> }));

import SystemPage from "./page";

describe("SystemPage", () => {
  beforeEach(() => {
    getSystemHealth.mockReset();
    getRetentionStatus.mockReset();
    getRetentionStatus.mockResolvedValue({ enabled: true, retention_days: 7, cutoff: "2026-09-08T00:00:00Z", eligible_trace_count: 0, stored_trace_count: 1 });
  });

  it("renders waiting ingestion and queue state", async () => {
    getSystemHealth.mockResolvedValue({ overall_status: "WAITING_FOR_TELEMETRY", backend: { status: "HEALTHY" }, storage: { status: "HEALTHY" }, ingestion: { status: "WAITING_FOR_TELEMETRY", last_telemetry_received_at: null }, analysis: { status: "HEALTHY", pending_jobs: 0, running_jobs: 0, failed_jobs_recent: 0, oldest_pending_job_age_ms: null } });
    render(await SystemPage());

    expect(screen.getAllByText("WAITING_FOR_TELEMETRY")).toHaveLength(2);
    expect(screen.getByText("PostgreSQL connectivity")).toBeInTheDocument();
    expect(screen.getByText("Oldest pending age")).toBeInTheDocument();
    expect(screen.getByText("Retention eligible: 0")).toBeInTheDocument();
  });

  it("renders degraded analysis and API failure safely", async () => {
    getSystemHealth.mockResolvedValue({ overall_status: "DEGRADED", backend: { status: "HEALTHY" }, storage: { status: "HEALTHY" }, ingestion: { status: "HEALTHY", last_telemetry_received_at: "2026-09-11T12:00:00Z" }, analysis: { status: "DEGRADED", pending_jobs: 1, running_jobs: 0, failed_jobs_recent: 1, oldest_pending_job_age_ms: 31_000 } });
    const { unmount } = render(await SystemPage());
    expect(screen.getAllByText("DEGRADED")).toHaveLength(2);
    expect(screen.getByText("31.0 s")).toBeInTheDocument();

    unmount();
    getSystemHealth.mockRejectedValueOnce(new Error("offline"));
    render(await SystemPage());
    expect(screen.getByText("TraceForge system status is unavailable.")).toBeInTheDocument();
  });

  it("keeps health visible when retention status is unavailable", async () => {
    getSystemHealth.mockResolvedValue({ overall_status: "HEALTHY", backend: { status: "HEALTHY" }, storage: { status: "HEALTHY" }, ingestion: { status: "HEALTHY", last_telemetry_received_at: "2026-09-11T12:00:00Z" }, analysis: { status: "HEALTHY", pending_jobs: 0, running_jobs: 0, failed_jobs_recent: 0, oldest_pending_job_age_ms: null } });
    getRetentionStatus.mockRejectedValueOnce(new Error("offline"));

    render(await SystemPage());
    expect(screen.getByText("Retention status is unavailable.")).toBeInTheDocument();
  });
});
