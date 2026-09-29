export type Provider = "anthropic" | "ollama";

export type Lang = "en" | "ar";
export type LanguageChoice = Lang | "auto";

export type ChartType = "line" | "bar" | "stat";

/** Postgres numerics are widened to float at the API boundary; dates arrive as ISO strings. */
export type Cell = string | number | boolean | null;

export interface QueryRequest {
  question: string;
  language?: LanguageChoice;
  provider?: Provider | null;
  dry_run?: boolean;
}

export interface ChartSpec {
  type: ChartType;
  x_key: string | null;
  y_keys: string[];
  title: string;
}

export interface QueryResponse {
  answer: string;
  language: Lang;
  outcome: "answer" | "no_data";
  answer_limited: boolean;
  snapshot_id: string | null;
  date_conditions: string[];
  sql: string;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  truncation_reason: "row_limit" | "cell_size" | "result_bytes" | null;
  chart: ChartSpec | null;
  tables_used: string[];
  retry_count: number;
  latency_ms: number;
  provider: string;
  query_method?: string;
}

export interface ExampleQuestion {
  id: string;
  lang: Lang;
  text: string;
}

export interface ExamplesResponse {
  examples: ExampleQuestion[];
}

export interface ErrorPayload {
  error: string;
  detail: string;
  request_id?: string | null;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  allowed_values?: string[];
}

export interface SchemaForeignKey {
  name: string | null;
  columns: string[];
  referred_schema: string | null;
  referred_table: string | null;
  referred_columns: string[];
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
  primary_key: string[];
  foreign_keys: SchemaForeignKey[];
}

export interface SchemaResponse {
  schema: string;
  snapshot_id: string;
  tables: SchemaTable[];
  coverage: SourceCoverage[];
}

export interface SourceCoverage {
  source_file: string;
  grain: string | null;
  measure: string | null;
  observed_from: string | null;
  observed_through: string | null;
  complete_through: string | null;
}

/** Codes the pipeline and the route can return in `ErrorPayload.error`. */
export type ApiErrorCode =
  | "PARSE_ERROR"
  | "VALIDATION_ERROR"
  | "SCOPE_ERROR"
  | "UNSAFE_SQL"
  | "UNSUPPORTED"
  | "CLARIFICATION"
  | "EMPTY_RESPONSE"
  | "EXECUTION_ERROR"
  | "DATABASE_BUSY"
  | "QUERY_TIMEOUT"
  | "RESULT_TOO_LARGE"
  | "MODEL_BUSY"
  | "SERVER_BUSY"
  | "SESSION_RATE_LIMIT"
  | "SESSION_DAILY_LIMIT"
  | "IP_RATE_LIMIT"
  | "IP_DAILY_LIMIT"
  | "LIMITER_UNAVAILABLE"
  | "REQUEST_TIMEOUT"
  | "UNKNOWN_PROVIDER"
  | "PROVIDER_UNAVAILABLE"
  | "LANGUAGE_MISMATCH"
  | "INVALID_REQUEST"
  | "UPSTREAM_ERROR"
  | "NETWORK_ERROR";
