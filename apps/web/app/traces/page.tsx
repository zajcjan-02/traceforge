import { TraceList } from "../../components/trace-list";
import { getServices, getTraces } from "../../lib/api";

const keys = [
  "trace_id", "service_id", "root_operation", "completeness_state", "analysis_state",
  "min_duration_ns", "max_duration_ns", "has_findings", "finding_type", "min_severity",
  "start_time_from_ns", "start_time_to_ns", "order", "cursor",
];

export const dynamic = "force-dynamic";

export default async function TracesPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const values = await searchParams;
  const query = new URLSearchParams();
  for (const key of keys) if (values[key]) query.set(key, values[key]!);
  const filters = Object.fromEntries([...query].filter(([key]) => key !== "cursor"));
  try {
    const [{ items: traces, next_cursor }, { items: services }] = await Promise.all([
      getTraces(query),
      getServices(),
    ]);
    const next = new URLSearchParams(filters);
    if (next_cursor) next.set("cursor", next_cursor);
    return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12"><h1 className="mb-4 text-2xl font-semibold">Traces</h1><TraceList filters={filters} key={query.toString()} nextHref={next_cursor ? `/traces?${next}` : null} services={services} traces={traces} /></section>;
  } catch {
    return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12"><h1 className="mb-4 text-2xl font-semibold">Traces</h1><p className="rounded-md border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>;
  }
}
