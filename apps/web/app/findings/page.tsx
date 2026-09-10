import Link from "next/link";

import { getFindings } from "../../lib/api";

const labels: Record<string, string> = { REPEATED_DATABASE_OPERATION: "Repeated database operation", MAJOR_LATENCY_CONTRIBUTOR: "Major latency contributor", LIKELY_ERROR_ORIGIN: "Likely error origin", REPEATED_DOWNSTREAM_OPERATION: "Repeated downstream operation" };

export const dynamic = "force-dynamic";

export default async function FindingsPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["type", "severity", "confidence", "cursor"]) if (params[key]) query.set(key, params[key]!);
  try {
    const data = await getFindings(query);
    const next = new URLSearchParams();
    for (const key of ["type", "severity", "confidence"]) if (params[key]) next.set(key, params[key]!);
    if (data.next_cursor) next.set("cursor", data.next_cursor);
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><h1 className="mb-4 text-2xl font-semibold">Findings</h1><form method="get" className="mb-4 flex gap-3"><select name="type" defaultValue={params.type}><option value="">All types</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select name="severity" defaultValue={params.severity}><option value="">All severity</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select><select name="confidence" defaultValue={params.confidence}><option value="">All confidence</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select><button className="text-forge-accent">Filter</button></form>{data.items.length ? <div className="rounded border border-forge-border">{data.items.map((finding) => <Link className="block border-t border-forge-border p-3 text-forge-text hover:bg-forge-base/70" href={`/traces/${finding.trace_id}?finding=${finding.finding_id}`} key={finding.finding_id}><span className="text-forge-highlight">{finding.severity}</span> <span className="text-forge-accent">{finding.confidence}</span> <strong className="ml-2">{labels[finding.type] ?? finding.title}</strong><p className="m-1 text-forge-muted">{finding.service && `${finding.service} · `}{finding.summary}</p><code className="text-xs text-forge-muted">{finding.trace_id}</code></Link>)}</div> : <p className="rounded border border-forge-border p-4 text-forge-muted">No current diagnostic findings.</p>}{data.next_cursor && <Link className="mt-4 inline-block text-forge-accent" href={`/findings?${next}`}>Next</Link>}</section>;
  } catch { return <section className="mx-auto max-w-[1440px] px-6 py-7"><p className="rounded border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>; }
}
