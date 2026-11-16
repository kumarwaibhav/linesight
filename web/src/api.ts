// Typed contracts keep the redesigned UI aligned with the existing FastAPI service.
export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  service: string;
  version: string;
}

export interface ModelResponse {
  name: string;
  algorithm: string;
  category: string;
  model_version: string | null;
  threshold: number | null;
  max_image_bytes: number;
  history_mode: "local" | "temporary" | string;
  score_semantics: string;
  heatmap_semantics: string;
  deployment_scope: string;
}

export interface MetricReport {
  auroc?: number;
  average_precision?: number;
  precision?: number;
  recall?: number;
  f1?: number;
}

export interface MetricsResponse {
  available: boolean;
  report: MetricReport;
}

export interface Sample {
  id: string;
  filename: string;
  defect_type: string;
  label: number;
  image_url: string;
}

export interface SamplesResponse {
  mode: string;
  count: number;
  samples: Sample[];
}

export interface InspectionResult {
  score: number;
  threshold: number;
  is_anomaly: boolean;
  model_version: string;
  inference_ms: number;
  width: number;
  height: number;
  heatmap: number[][];
  filename?: string;
  source_id?: string;
  timestamp?: string;
}

export interface EventRecord {
  id: string;
  timestamp: string;
  source_id: string;
  frame_id: string | null;
  filename: string;
  score: number;
  threshold: number;
  is_anomaly: boolean;
  inference_ms: number;
  model_version: string;
}

export interface EventsResponse {
  events: EventRecord[];
  retained_total: number;
  retained_alerts: number;
  retention_limit: number;
}

// Use same-origin, no-store requests so local, Vercel, and self-hosted installs behave alike.
export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, cache: "no-store" });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error(`The service returned HTTP ${response.status}.`);
  }
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : "The request could not be processed.";
    throw new Error(detail);
  }
  return body as T;
}

// The model receives bytes through the existing multipart inspection route.
export async function inspectImage(
  blob: Blob,
  filename: string,
  sourceId: string,
  frameId?: string,
): Promise<InspectionResult> {
  const form = new FormData();
  form.append("file", blob, filename);
  form.append("source_id", sourceId);
  if (frameId) form.append("frame_id", frameId);
  return apiRequest<InspectionResult>("/api/inspect", { method: "POST", body: form });
}
