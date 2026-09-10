export type Timing = string | null;
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type TraceSummary = {
  trace_id: string;
  revision: number;
  start_time_unix_ns: string;
  end_time_unix_ns: Timing;
  duration_ns: Timing;
  span_count: number;
  service_count: number;
  completeness_state: string;
  analysis_state: string | null;
};

export type Span = {
  span_id: string;
  parent_span_id: string | null;
  service: { name: string; namespace: string } | null;
  name: string;
  span_kind: string;
  start_time_unix_ns: string;
  end_time_unix_ns: Timing;
  duration_ns: Timing;
  status: string;
  attributes: Record<string, JsonValue>;
  resource_attributes: Record<string, JsonValue>;
  events: Array<{
    event_index: number;
    name: string;
    timestamp_unix_ns: Timing;
    attributes: Record<string, JsonValue>;
  }>;
};

export type Finding = {
  finding_id: string;
  type: string;
  severity: string;
  confidence: string;
  title: string;
  summary: string;
  observation: string | null;
  interpretation: string | null;
  structured_data: Record<string, JsonValue>;
  related_span_ids: string[];
  evidence: Array<{
    type: string;
    description: string | null;
    structured_data: Record<string, JsonValue>;
  }>;
};

export type TraceDetail = {
  trace: TraceSummary & {
    last_received_at: string;
    services: Array<{ service_id: number; name: string; namespace: string }>;
  };
  analysis: {
    state: string | null;
    current_run: {
      analysis_run_id: string;
      trace_revision: number;
      state: string;
      detector_results: Array<{
        detector_id: string;
        detector_version: string;
        state: string;
        duration_ns: string;
        failure_reason: string | null;
      }>;
      findings: Finding[];
    } | null;
  };
  spans: Span[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const baseUrl = process.env.TRACEFORGE_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, `TraceForge API request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export async function getTraces() {
  return request<{ items: TraceSummary[] }>("/api/v1/traces");
}

export async function getTrace(traceId: string) {
  return request<TraceDetail>(`/api/v1/traces/${traceId}`);
}
