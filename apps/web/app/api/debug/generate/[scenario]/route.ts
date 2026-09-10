import { NextResponse } from "next/server";

const scenarios = new Set([
  "normal",
  "repeated-db",
  "critical-path",
  "latency-contributor",
  "propagated-error",
  "independent-errors",
  "service-dependency",
  "repeated-downstream",
]);

export async function POST(_: Request, { params }: { params: Promise<{ scenario: string }> }) {
  const { scenario } = await params;
  if (!scenarios.has(scenario)) return NextResponse.json({ detail: "Unknown debug scenario." }, { status: 404 });

  const baseUrl = process.env.TRACEFORGE_API_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${baseUrl}/debug/generate/${scenario}`, { method: "POST" });
  return new Response(await response.text(), {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
