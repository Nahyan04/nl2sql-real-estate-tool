import type { ApiError } from "@/lib/api";
import type { ApiErrorCode } from "@/lib/types";

const EXPLANATIONS: Record<ApiErrorCode, { title: string; guidance: string }> = {
  PARSE_ERROR: {
    title: "No query produced",
    guidance: "The model did not return usable SQL. Name the measure and the time range you want.",
  },
  EMPTY_RESPONSE: {
    title: "No query produced",
    guidance: "The model returned nothing. Ask again, or rephrase the question more directly.",
  },
  VALIDATION_ERROR: {
    title: "Query rejected",
    guidance: "The generated SQL did not parse. Try a narrower question over one subject.",
  },
  UNSAFE_SQL: {
    title: "Query rejected",
    guidance: "The generated SQL was not read-only, so it was never run. Rephrase as a question about the data.",
  },
  UNSUPPORTED: {
    title: "That calculation is not supported",
    guidance: "The verified exports do not support that question. Try a source-backed sales, rent, index, or indicative gross segment yield question.",
  },
  CLARIFICATION: {
    title: "Please clarify the question",
    guidance: "Give exact dates or a named reporting period, and specify any ambiguous source place name.",
  },
  EXECUTION_ERROR: {
    title: "Query failed to run",
    guidance: "The database rejected the query. A shorter time range or fewer joins usually fixes it.",
  },
  DATABASE_BUSY: {
    title: "Database is busy",
    guidance: "Too many queries are running. Try again in a moment or narrow the question.",
  },
  QUERY_TIMEOUT: {
    title: "Query took too long",
    guidance: "Use a shorter time range or a more specific subject so the database can finish the query.",
  },
  RESULT_TOO_LARGE: {
    title: "Result is too large",
    guidance: "Add a filter, time range, or grouping so the response contains less data.",
  },
  MODEL_BUSY: {
    title: "Model is busy",
    guidance: "The inference queue is full. Try again in a moment.",
  },
  SERVER_BUSY: {
    title: "Too many analyses at once",
    guidance: "The demo is busy. Wait a moment and try your question again.",
  },
  SESSION_RATE_LIMIT: {
    title: "Brief pause",
    guidance: "This browser has sent many questions in a short time. Try again after the pause.",
  },
  SESSION_DAILY_LIMIT: {
    title: "Browser allowance reached",
    guidance: "This browser has reached its daily demo allowance.",
  },
  IP_RATE_LIMIT: {
    title: "Brief pause",
    guidance: "Many questions are coming from this network. Try again after the pause.",
  },
  IP_DAILY_LIMIT: {
    title: "Network allowance reached",
    guidance: "This network has reached its daily demo allowance.",
  },
  LIMITER_UNAVAILABLE: {
    title: "Demo temporarily unavailable",
    guidance: "The request guard could not be checked. Try again shortly.",
  },
  REQUEST_TIMEOUT: {
    title: "Request timed out",
    guidance: "The full analysis exceeded its time limit. Try a narrower question.",
  },
  UNKNOWN_PROVIDER: {
    title: "Model not configured",
    guidance: "The server does not have that model option set up.",
  },
  PROVIDER_UNAVAILABLE: {
    title: "Model temporarily unavailable",
    guidance: "The selected provider could not complete the analysis. Keep your question and try again when that provider is online.",
  },
  INVALID_REQUEST: {
    title: "Check your request",
    guidance: "Enter a question and choose one of the available providers.",
  },
  UPSTREAM_ERROR: {
    title: "Request failed upstream",
    guidance: "The model provider or the database did not respond. For Self-hosted, check that the configured Ollama server is running.",
  },
  NETWORK_ERROR: {
    title: "API unreachable",
    guidance: "Nothing answered at the API address. Check that the backend is running.",
  },
};

export function ErrorPanel({ error, question, onRetry }: { error: ApiError; question: string; onRetry: () => void }) {
  const arabicOutcome = (error.code === "UNSUPPORTED" || error.code === "CLARIFICATION") && /[\u0600-\u06FF]/.test(question);
  const explanation = arabicOutcome ? {
    title: error.code === "CLARIFICATION" ? "يرجى توضيح السؤال" : "هذا السؤال غير مدعوم",
    guidance: error.code === "CLARIFICATION"
      ? "حدد فترة زمنية دقيقة واسم مكان واضح كما يظهر في المصدر."
      : "البيانات المتاحة لا تدعم هذا السؤال. يمكنك السؤال عن المبيعات أو الإيجارات أو المؤشرات أو تقدير العائد الإجمالي للمجموعة.",
  } : EXPLANATIONS[error.code] ?? {
    title: "Request failed",
    guidance: "Something went wrong before an answer could be produced.",
  };

  return (
    <section dir={arabicOutcome ? "rtl" : undefined} className="mt-12 border-s-2 border-destructive ps-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="label-mono text-destructive">{explanation.title}</h2>
        <span className="label-mono text-sand">{error.code}</span>
      </div>
      <p className="mt-2 max-w-[44rem] text-[1.0625rem] leading-relaxed text-ink">
        {explanation.guidance}
        {error.retryAfter !== null ? ` Retry after ${error.retryAfter} seconds.` : ""}
      </p>
      {error.detail && !arabicOutcome ? (
        <p className="mt-3 max-w-[44rem] font-mono text-[0.9375rem] leading-relaxed break-words text-sand">
          {error.detail}
        </p>
      ) : null}
      {error.requestId ? <p className="mt-3 label-mono text-sand">Request ID: {error.requestId}</p> : null}
      <button type="button" onClick={onRetry} className="mt-5 cursor-pointer rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-sage hover:text-sage">
        {arabicOutcome ? "حاول مرة أخرى" : "Try again"}
      </button>
    </section>
  );
}
