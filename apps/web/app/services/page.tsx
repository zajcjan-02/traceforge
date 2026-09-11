import { ServiceList } from "../../components/service-list";
import { getServices } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function ServicesPage() {
  try {
    const { items } = await getServices();
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><h1 className="mb-4 text-2xl font-semibold">Services</h1><ServiceList services={items} /></section>;
  } catch {
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><p className="rounded border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>;
  }
}
