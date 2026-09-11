import { notFound } from "next/navigation";

import { TraceView } from "../../../components/trace-view";
import { ApiError, getTrace } from "../../../lib/api";

export const dynamic = "force-dynamic";

export default async function TracePage({ params, searchParams }: { params: Promise<{ traceId: string }>; searchParams: Promise<{ finding?: string }> }) {
  const { traceId } = await params;
  const { finding } = await searchParams;
  try {
    return <TraceView detail={await getTrace(traceId)} initialFindingId={finding} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><p className="rounded-md border border-forge-highlight/70 p-4 text-forge-highlight">TraceForge API is unavailable.</p></section>;
  }
}
