import { TraceList } from "../../components/trace-list";
import { getTraces } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function TracesPage() {
  try {
    const { items } = await getTraces();
    return <section className="page"><h1>Traces</h1><TraceList traces={items} /></section>;
  } catch {
    return <section className="page"><h1>Traces</h1><p className="page-state error">TraceForge API is unavailable.</p></section>;
  }
}
