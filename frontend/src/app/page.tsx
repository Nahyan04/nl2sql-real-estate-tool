"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { AnswerPanel } from "@/components/answer-panel";
import { DataSurface } from "@/components/data-surface";
import { ErrorPanel } from "@/components/error-panel";
import { ExampleQuestions } from "@/components/example-questions";
import { Header } from "@/components/header";
import { HistoryPanel } from "@/components/history-panel";
import { PipelineTrace } from "@/components/pipeline-trace";
import { QueryInput } from "@/components/query-input";
import { ResultChart } from "@/components/result-chart";
import { ResultsTable } from "@/components/results-table";
import { SqlPanel } from "@/components/sql-panel";
import { ApiError, getExamples, getSchema, postQuery } from "@/lib/api";
import { clearHistory, getHistory, getServerHistory, pushHistory, subscribeHistory } from "@/lib/history";
import type { ExampleQuestion, Provider, QueryResponse, SchemaTable } from "@/lib/types";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const history = useSyncExternalStore(subscribeHistory, getHistory, getServerHistory);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState(0);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getExamples(controller.signal)
      .then((response) => setExamples(response.examples))
      .catch(() => setExamples([]));
    getSchema(controller.signal)
      .then((response) => setTables(response.tables))
      .catch(() => setTables([]));
    return () => controller.abort();
  }, []);

  const run = useCallback(
    async (text: string) => {
      const asked = text.trim();
      if (!asked) return;

      pending.current?.abort();
      const controller = new AbortController();
      pending.current = controller;

      setQuestion(asked);
      setBusy(true);
      setError(null);
      setResult(null);
      setRunId((id) => id + 1);
      pushHistory(asked);

      try {
        setResult(await postQuery({ question: asked, provider }, controller.signal));
      } catch (cause) {
        if (cause instanceof Error && cause.name === "AbortError") return;
        setError(cause instanceof ApiError ? cause : new ApiError("UPSTREAM_ERROR", String(cause), 0));
      } finally {
        if (pending.current === controller) setBusy(false);
      }
    },
    [provider],
  );

  const showTrace = busy || result !== null;

  return (
    <>
      <Header provider={provider} onProviderChange={setProvider} busy={busy} />

      <main className="mx-auto w-full max-w-[68rem] flex-1 px-5 sm:px-8 pt-16 pb-24">
        <QueryInput value={question} onChange={setQuestion} onSubmit={() => run(question)} busy={busy} />

        {showTrace ? (
          <div className="mt-10">
            <PipelineTrace
              key={runId}
              state={busy ? "running" : "done"}
              attempts={(result?.retry_count ?? 0) + 1}
            />
          </div>
        ) : error ? null : (
          <>
            <ExampleQuestions examples={examples} onPick={run} busy={busy} />
            <DataSurface tables={tables} />
          </>
        )}

        {error ? <ErrorPanel error={error} /> : null}

        {result ? (
          <>
            <AnswerPanel answer={result.answer} />
            {result.chart ? (
              <ResultChart chart={result.chart} columns={result.columns} rows={result.rows} />
            ) : null}
            {/* a scalar is already shown whole by the stat figure */}
            {result.chart?.type === "stat" && result.columns.length === 1 ? null : (
              <ResultsTable
                columns={result.columns}
                rows={result.rows}
                rowCount={result.row_count}
                truncated={result.truncated}
              />
            )}
            <SqlPanel
              sql={result.sql}
              tablesUsed={result.tables_used}
              retryCount={result.retry_count}
              latencyMs={result.latency_ms}
              provider={result.provider}
            />
          </>
        ) : null}

        <HistoryPanel questions={history} onPick={run} onClear={clearHistory} busy={busy} />
      </main>
    </>
  );
}
