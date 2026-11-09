export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TraceStep = { step: "schema" | "generate" | "validate" | "execute" | "repair" | "summarize"; status: "ok" | "warn" | "error"; ms: number; detail: string };
export type Tile = { label: string; value: string | number | null; kind: "number" | "text"; sub?: string | null };
export type ChartType = "bar" | "line" | "donut" | "grid" | "stat";
export type Chart = { type: ChartType; x: string | null; series: string[]; data: Record<string, string | number | null>[]; stacked?: boolean; available: ChartType[] };
export type Cell = string | number | boolean | null;

export type AskResult = {
  id?: string;
  question: string;
  status: "ok" | "failed" | "unanswerable";
  summary: string | null;
  sql: string;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  chart: Chart | null;
  tiles: Tile[];
  trace: TraceStep[];
  retrieved_tables: string[];
  tables_used: string[];
  repairs: number;
  first_error: string | null;
  error: string | null;
  unanswerable: boolean;
  latency_ms: number;
};

export type Health = {
  status: string;
  llm: { configured: boolean; model: string; provider: string };
  database: { name: string; dialect: string; tables: number; columns: number; latency_ms: number } | { error: string } | null;
};

export type SchemaColumn = { name: string; type: string; nullable: boolean; primary_key: boolean; comment: string | null; fk: string | null; sample_values: string[]; value_range: [string, string] | null };
export type SchemaTable = { name: string; comment: string | null; row_count: number; columns: SchemaColumn[] };
export type Relationship = { from_table: string; from_column: string; to_table: string; to_column: string };
export type SchemaInfo = { database: string; built_at: number; tables: SchemaTable[]; relationships: Relationship[] };
export type HistoryItem = { id: string; created_at: number; question: string; status: string };

export type EvalSummary = {
  key: string; label: string; description: string; n: number; correct: number; accuracy: number;
  median_latency_ms: number; p95_latency_ms: number; repair_rate: number; healed: number;
  invalid_sql: number; wrong_result: number; refused: number;
  categories: Record<string, { n: number; correct: number; accuracy: number }>;
};
export type EvalRecord = {
  config: string; case_id: string; category: string; question: string; correct: boolean; failure: string | null;
  repairs: number; healed: boolean; latency_ms: number; error: string | null; first_error: string | null;
  expected_sql: string; actual_sql: string;
};
export type EvalRun = {
  id: string | null; status: "none" | "running" | "complete" | "failed" | "interrupted"; created_at?: number;
  progress: { done?: number; total?: number; config?: string; case?: string; error?: string };
  result: { n_cases: number; summary: EvalSummary[]; records: EvalRecord[]; finished_at: number } | null;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }, cache: "no-store" });
  } catch {
    throw new ApiError(0, `Cannot reach the AskData API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<Health>("/api/health"),
  examples: () => req<string[]>("/api/examples"),
  schema: () => req<SchemaInfo>("/api/schema"),
  refreshSchema: () => req<{ tables: number; built_at: number }>("/api/schema/refresh", { method: "POST" }),
  ask: (question: string) => req<AskResult>("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
  history: () => req<HistoryItem[]>("/api/history?limit=8"),
  historyItem: (id: string) => req<AskResult>(`/api/history/${id}`),
  evalLatest: () => req<EvalRun>("/api/eval/latest"),
  evalInfo: () => req<{ cases: number; categories: Record<string, number>; llm: Health["llm"] }>("/api/eval/info"),
  evalRun: (limit?: number) => req<{ id: string }>("/api/eval/run", { method: "POST", body: JSON.stringify(limit ? { limit } : {}) }),
};
