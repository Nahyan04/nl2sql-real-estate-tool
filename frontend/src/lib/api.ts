import type {
  ApiErrorCode,
  ErrorPayload,
  ExamplesResponse,
  QueryRequest,
  QueryResponse,
  SchemaResponse,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly detail: string;
  readonly status: number;

  constructor(code: ApiErrorCode, detail: string, status: number) {
    super(detail || code);
    this.name = "ApiError";
    this.code = code;
    this.detail = detail;
    this.status = status;
  }
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return typeof value === "object" && value !== null && typeof (value as ErrorPayload).error === "string";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${API_PREFIX}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (cause) {
    // a caller-initiated abort is not a failure — let it through untouched
    if (cause instanceof Error && cause.name === "AbortError") throw cause;
    throw new ApiError("NETWORK_ERROR", cause instanceof Error ? cause.message : "Cannot reach the API", 0);
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isErrorPayload(body)) {
      throw new ApiError(body.error as ApiErrorCode, body.detail, response.status);
    }
    throw new ApiError("UPSTREAM_ERROR", `Request failed with status ${response.status}`, response.status);
  }

  return body as T;
}

export function postQuery(payload: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function getExamples(signal?: AbortSignal): Promise<ExamplesResponse> {
  return request<ExamplesResponse>("/examples", { signal });
}

export function getSchema(signal?: AbortSignal): Promise<SchemaResponse> {
  return request<SchemaResponse>("/schema", { signal });
}
