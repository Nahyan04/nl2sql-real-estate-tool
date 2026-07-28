export type Provider = "anthropic" | "ollama";

export type Lang = "en" | "ar";

export type ChartType = "line" | "bar" | "stat";

/** Postgres numerics are widened to float at the API boundary; dates arrive as ISO strings. */
export type Cell = string | number | boolean | null;

export interface QueryRequest {
  question: string;
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
  sql: string;
  columns: string[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  chart: ChartSpec | null;
  tables_used: string[];
  retry_count: number;
  latency_ms: number;
  provider: string;
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
  tables: SchemaTable[];
}

/** Codes the pipeline and the route can return in `ErrorPayload.error`. */
export type ApiErrorCode =
  | "PARSE_ERROR"
  | "VALIDATION_ERROR"
  | "UNSAFE_SQL"
  | "EMPTY_RESPONSE"
  | "EXECUTION_ERROR"
  | "UNKNOWN_PROVIDER"
  | "UPSTREAM_ERROR"
  | "NETWORK_ERROR";
