import { NextResponse } from "next/server";

export async function POST() {
  const baseUrl = process.env.TRACEFORGE_API_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${baseUrl}/api/v1/system/retention/run`, { method: "POST" });
  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}
