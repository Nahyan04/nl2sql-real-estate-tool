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
  EXECUTION_ERROR: {
    title: "Query failed to run",
    guidance: "The database rejected the query. A shorter time range or fewer joins usually fixes it.",
  },
  UNKNOWN_PROVIDER: {
    title: "Model not configured",
    guidance: "The server does not have that model option set up.",
  },
  UPSTREAM_ERROR: {
    title: "Request failed upstream",
    guidance: "The model provider or the database did not respond. On On-prem, check that a local model server is running.",
  },
  NETWORK_ERROR: {
    title: "API unreachable",
    guidance: "Nothing answered at the API address. Check that the backend is running.",
  },
};

export function ErrorPanel({ error }: { error: ApiError }) {
  const explanation = EXPLANATIONS[error.code] ?? {
    title: "Request failed",
    guidance: "Something went wrong before an answer could be produced.",
  };

  return (
    <section className="mt-12 border-s-2 border-destructive ps-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="label-mono text-destructive">{explanation.title}</h2>
        <span className="label-mono text-sand/50">{error.code}</span>
      </div>
      <p className="mt-2 max-w-[44rem] text-[0.9375rem] leading-relaxed text-limestone">
        {explanation.guidance}
      </p>
      {error.detail ? (
        <p className="mt-3 max-w-[44rem] font-mono text-[0.8125rem] leading-relaxed break-words text-sand/70">
          {error.detail}
        </p>
      ) : null}
    </section>
  );
}
