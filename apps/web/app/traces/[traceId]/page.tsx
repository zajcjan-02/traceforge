import { notFound } from "next/navigation";

import { TraceView } from "../../../components/trace-view";
import { ApiError, getTrace } from "../../../lib/api";

export const dynamic = "force-dynamic";

export default async function TracePage({ params }: { params: Promise<{ traceId: string }> }) {
  const { traceId } = await params;
  try {
    return <TraceView detail={await getTrace(traceId)} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <section className="mx-auto max-w-[1440px] px-6 py-7"><p className="rounded-md border border-red-300/50 p-4 text-red-100">TraceForge API is unavailable.</p></section>;
  }
}
