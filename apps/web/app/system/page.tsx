import { getSystemHealth } from "../../lib/api";

export const dynamic = "force-dynamic";

function age(value: number | null) {
  if (value === null) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

function Panel({ title, status, children }: { title: string; status: string; children?: React.ReactNode }) {
  const accent = status === "DEGRADED" || status === "UNAVAILABLE" ? "text-forge-highlight" : status === "WAITING_FOR_TELEMETRY" ? "text-forge-muted" : "text-forge-accent";
  return <section className="rounded border border-forge-border bg-forge-panel p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">{title}</h2><span className={`text-sm font-medium ${accent}`}>{status}</span></div>{children}</section>;
}

export default async function SystemPage() {
  try {
    const health = await getSystemHealth();
    return <section className="mx-auto max-w-[1100px] px-6 py-7"><h1 className="mb-4 text-2xl font-semibold">System</h1><div className="grid gap-4 md:grid-cols-2"><Panel title="TraceForge" status={health.overall_status}><p className="text-forge-muted">Product operational status</p></Panel><Panel title="Storage" status={health.storage.status}><p className="text-forge-muted">PostgreSQL connectivity</p></Panel><Panel title="Ingestion" status={health.ingestion.status}><p className="text-forge-muted">Last telemetry received</p><code className="mt-1 block text-sm">{health.ingestion.last_telemetry_received_at ?? "—"}</code></Panel><Panel title="Analysis" status={health.analysis.status}><dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm"><dt className="text-forge-muted">Pending jobs</dt><dd>{health.analysis.pending_jobs}</dd><dt className="text-forge-muted">Running jobs</dt><dd>{health.analysis.running_jobs}</dd><dt className="text-forge-muted">Recent failed jobs</dt><dd>{health.analysis.failed_jobs_recent}</dd><dt className="text-forge-muted">Oldest pending age</dt><dd>{age(health.analysis.oldest_pending_job_age_ms)}</dd></dl></Panel></div></section>;
  } catch {
    return <section className="mx-auto max-w-[1100px] px-6 py-7"><h1 className="mb-4 text-2xl font-semibold">System</h1><p className="rounded border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge system status is unavailable.</p></section>;
  }
}
