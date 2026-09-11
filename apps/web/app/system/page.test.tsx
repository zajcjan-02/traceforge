import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getSystemHealth = vi.hoisted(() => vi.fn());

vi.mock("../../lib/api", () => ({ getSystemHealth }));

import SystemPage from "./page";

describe("SystemPage", () => {
  beforeEach(() => getSystemHealth.mockReset());

  it("renders waiting ingestion and queue state", async () => {
    getSystemHealth.mockResolvedValue({ overall_status: "WAITING_FOR_TELEMETRY", backend: { status: "HEALTHY" }, storage: { status: "HEALTHY" }, ingestion: { status: "WAITING_FOR_TELEMETRY", last_telemetry_received_at: null }, analysis: { status: "HEALTHY", pending_jobs: 0, running_jobs: 0, failed_jobs_recent: 0, oldest_pending_job_age_ms: null } });
    render(await SystemPage());

    expect(screen.getByText("WAITING_FOR_TELEMETRY")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL connectivity")).toBeInTheDocument();
    expect(screen.getByText("Oldest pending age")).toBeInTheDocument();
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
});
