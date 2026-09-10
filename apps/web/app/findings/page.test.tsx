import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getFindings = vi.hoisted(() => vi.fn());

vi.mock("../../lib/api", () => ({ getFindings }));

import FindingsPage from "./page";

const finding = {
  finding_id: "finding-1",
  trace_id: "0123456789abcdef0123456789abcdef",
  type: "LIKELY_ERROR_ORIGIN",
  severity: "HIGH",
  confidence: "MEDIUM",
  title: "Likely error origin",
  summary: "An exception was observed.",
  created_at: "2026-09-10T12:00:00Z",
  service: "payment",
};

describe("FindingsPage", () => {
  beforeEach(() => getFindings.mockReset());

  it("renders readable findings and links to selected trace context", async () => {
    getFindings.mockResolvedValue({ items: [finding], next_cursor: null });
    render(await FindingsPage({ searchParams: Promise.resolve({}) }));

    expect(screen.getByText("Likely error origin", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("HIGH", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("MEDIUM", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText(/payment/)).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/traces/0123456789abcdef0123456789abcdef?finding=finding-1",
    );
  });

  it("shows empty and API failure states", async () => {
    getFindings.mockResolvedValue({ items: [], next_cursor: null });
    const { unmount } = render(await FindingsPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByText("No current diagnostic findings.")).toBeInTheDocument();

    unmount();
    getFindings.mockRejectedValueOnce(new Error("offline"));
    const page = await FindingsPage({ searchParams: Promise.resolve({}) });
    render(page);
    expect(screen.getByText("TraceForge API is unavailable.")).toBeInTheDocument();
  });

  it("passes filters and preserves them in the next-page link", async () => {
    getFindings.mockResolvedValue({ items: [finding], next_cursor: "opaque-cursor" });
    render(await FindingsPage({ searchParams: Promise.resolve({ type: "LIKELY_ERROR_ORIGIN", severity: "HIGH", confidence: "MEDIUM" }) }));

    expect(getFindings).toHaveBeenCalledWith(
      new URLSearchParams("type=LIKELY_ERROR_ORIGIN&severity=HIGH&confidence=MEDIUM"),
    );
    expect(screen.getByRole("link", { name: "Next" })).toHaveAttribute(
      "href",
      "/findings?type=LIKELY_ERROR_ORIGIN&severity=HIGH&confidence=MEDIUM&cursor=opaque-cursor",
    );
    expect(screen.getByRole("button", { name: "Filter" })).toBeInTheDocument();
  });
});
