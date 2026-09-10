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
    return <section className="page"><p className="page-state error">TraceForge API is unavailable.</p></section>;
  }
}
