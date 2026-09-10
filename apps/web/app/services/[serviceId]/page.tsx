import { notFound } from "next/navigation";

import { ServiceView } from "../../../components/service-view";
import { ApiError, getService, getServiceDependencies } from "../../../lib/api";

export const dynamic = "force-dynamic";

export default async function ServicePage({ params }: { params: Promise<{ serviceId: string }> }) {
  const { serviceId } = await params;
  try {
    const [detail, dependencies] = await Promise.all([getService(serviceId), getServiceDependencies(serviceId)]);
    return <ServiceView {...detail} {...dependencies} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><p className="rounded border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>;
  }
}
