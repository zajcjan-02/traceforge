"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { RetentionStatus } from "../lib/api";

export function RetentionPanel({ retention }: { retention: RetentionStatus }) {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function runCleanup() {
    setRunning(true);
    setError("");
    try {
      const response = await fetch("/api/system/retention/run", { method: "POST" });
      if (!response.ok) throw new Error();
      router.refresh();
    } catch {
      setError("Cleanup could not be started.");
    } finally {
      setRunning(false);
    }
  }

  const status = retention.enabled
    ? retention.eligible_trace_count
      ? "ELIGIBLE TRACES"
      : "ENABLED"
    : "DISABLED";
  return <section className="rounded border border-forge-border bg-forge-panel p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Retention</h2><span className={retention.enabled ? "text-sm font-medium text-forge-accent" : "text-sm font-medium text-forge-muted"}>{status}</span></div><dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm"><dt className="text-forge-muted">Retention period</dt><dd>{retention.enabled ? `${retention.retention_days} days` : "Automatic cleanup disabled"}</dd><dt className="text-forge-muted">Stored traces</dt><dd>{retention.stored_trace_count}</dd><dt className="text-forge-muted">Eligible traces</dt><dd>{retention.eligible_trace_count}</dd><dt className="text-forge-muted">Cutoff</dt><dd><code>{retention.cutoff ?? "—"}</code></dd></dl>{retention.enabled && <button className="mt-4 rounded border border-forge-highlight px-3 py-1.5 text-sm text-forge-highlight disabled:opacity-50" disabled={running} onClick={runCleanup}>{running ? "Running cleanup..." : "Run cleanup"}</button>}{error && <p className="mt-2 text-sm text-forge-highlight">{error}</p>}</section>;
}
