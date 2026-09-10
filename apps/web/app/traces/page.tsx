import { TraceList } from "../../components/trace-list";
import { getTraces } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function TracesPage() {
  try {
    const { items } = await getTraces();
    return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12"><h1 className="mb-4 text-2xl font-semibold">Traces</h1><TraceList traces={items} /></section>;
  } catch {
    return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12"><h1 className="mb-4 text-2xl font-semibold">Traces</h1><p className="rounded-md border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>;
  }
}
