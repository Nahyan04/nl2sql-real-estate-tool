"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { AnswerPanel } from "@/components/answer-panel";
import { DataSurface } from "@/components/data-surface";
import { ErrorPanel } from "@/components/error-panel";
import { ExampleQuestions } from "@/components/example-questions";
import { Header } from "@/components/header";
import { HistoryPanel } from "@/components/history-panel";
import { ProcessOverview } from "@/components/process-overview";
import { EvidencePanel } from "@/components/evidence-panel";
import { QueryInput } from "@/components/query-input";
import { ResultChart } from "@/components/result-chart";
import { ResultsTable } from "@/components/results-table";
import { SqlPanel } from "@/components/sql-panel";
import { ApiError, getExamples, getSchema, postQuery } from "@/lib/api";
import { resolveLanguage } from "@/lib/language";
import { clearHistory, getHistory, getServerHistory, pushHistory, subscribeHistory } from "@/lib/history";
import type { ExampleQuestion, Lang, LanguageChoice, Provider, QueryResponse, SchemaTable, SourceCoverage } from "@/lib/types";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [languageChoice, setLanguageChoice] = useState<LanguageChoice>("auto");
  const [activeLanguage, setActiveLanguage] = useState<Lang>("en");
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [coverage, setCoverage] = useState<SourceCoverage[]>([]);
  const [schemaSnapshotId, setSchemaSnapshotId] = useState<string | null>(null);
  const history = useSyncExternalStore(subscribeHistory, getHistory, getServerHistory);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState(0);
  const [startedAt, setStartedAt] = useState(0);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getExamples(controller.signal)
      .then((response) => setExamples(response.examples))
      .catch(() => setExamples([]));
    getSchema(controller.signal)
      .then((response) => {
        setTables(response.tables);
        setCoverage(response.coverage ?? []);
        setSchemaSnapshotId(response.snapshot_id);
      })
      .catch(() => setTables([]));
    return () => controller.abort();
  }, []);

  const run = useCallback(
    async (text: string) => {
      const asked = text.trim();
      if (!asked) return;
      const runLanguage = resolveLanguage(asked, languageChoice);

      pending.current?.abort();
      const controller = new AbortController();
      pending.current = controller;

      setQuestion(asked);
      setActiveLanguage(runLanguage);
      setBusy(true);
      setError(null);
      setResult(null);
      setRunId((id) => id + 1);
      setStartedAt(performance.now());
      pushHistory(asked);

      try {
        const response = await postQuery({ question: asked, provider, language: languageChoice }, controller.signal);
        if (pending.current === controller) setResult(response);
      } catch (cause) {
        if (cause instanceof Error && cause.name === "AbortError") return;
        if (pending.current === controller) setError(cause instanceof ApiError ? cause : new ApiError("UPSTREAM_ERROR", String(cause), 0));
      } finally {
        if (pending.current === controller) {
          pending.current = null;
          setBusy(false);
        }
      }
    },
    [provider, languageChoice],
  );

  const clearCurrent = useCallback(() => {
    pending.current?.abort();
    pending.current = null;
    setQuestion("");
    setResult(null);
    setError(null);
    setBusy(false);
    setRunId((id) => id + 1);
  }, []);

  const changeLanguage = (choice: LanguageChoice) => {
    setLanguageChoice(choice);
    if (result || error) {
      setResult(null);
      setError(null);
    }
  };

  const showProcess = busy || result !== null || error !== null;
  const arabicQuestion = (showProcess ? activeLanguage : resolveLanguage(question, languageChoice)) === "ar";

  useEffect(() => {
    document.documentElement.lang = arabicQuestion ? "ar" : "en";
  }, [arabicQuestion]);

  return (
    <>
      <Header provider={provider} language={languageChoice} arabic={arabicQuestion} onLanguageChange={changeLanguage} onProviderChange={setProvider} busy={busy} />

      <main dir={arabicQuestion ? "rtl" : "ltr"} className="mx-auto w-full max-w-[88rem] flex-1 px-5 pt-10 pb-20 sm:px-8 lg:px-12 lg:pt-14">
        <QueryInput value={question} onChange={setQuestion} onSubmit={() => run(question)} busy={busy} arabic={arabicQuestion} />
        {showProcess ? (
          <button type="button" onClick={clearCurrent}
            className="label-mono mt-4 cursor-pointer text-sand transition-colors hover:text-sage">
            {arabicQuestion ? "سؤال جديد" : "New question"}
          </button>
        ) : null}

        {busy ? (
          <ProcessOverview
            key={runId}
            startedAt={startedAt}
            arabic={arabicQuestion}
          />
        ) : !showProcess ? (
          <div className="mt-12 grid items-start gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,1.55fr)_minmax(19rem,0.85fr)]">
            <ExampleQuestions key={arabicQuestion ? "ar" : "en"} examples={examples} onPick={run} busy={busy} arabic={arabicQuestion} />
            <DataSurface tables={tables} arabic={arabicQuestion} />
          </div>
        ) : null}

        {error ? <ErrorPanel error={error} arabic={arabicQuestion} onRetry={() => run(question)} /> : null}

        {result ? (
          <>
            <div className="mt-12 grid items-start gap-x-10 gap-y-10 md:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.9fr)] xl:gap-x-12">
              <AnswerPanel answer={result.answer} arabic={arabicQuestion} title={result.outcome === "no_data"
                ? (arabicQuestion ? "لا توجد بيانات مطابقة" : "No matching data")
                : (arabicQuestion ? "الإجابة" : "Answer")} />
              <EvidencePanel result={result} coverage={coverage} schemaSnapshotId={schemaSnapshotId} arabic={arabicQuestion} />
            </div>
            {result.outcome !== "no_data" && result.chart ? (
              <ResultChart chart={result.chart} columns={result.columns} rows={result.rows} arabic={arabicQuestion} />
            ) : null}
            {/* a scalar is already shown whole by the stat figure */}
            {result.outcome === "no_data" || (result.chart?.type === "stat" && result.columns.length === 1) ? null : (
              <ResultsTable
                columns={result.columns}
                rows={result.rows}
                rowCount={result.row_count}
                truncated={result.truncated}
                truncationReason={result.truncation_reason}
                arabic={arabicQuestion}
              />
            )}
            <SqlPanel
              sql={result.sql}
              tablesUsed={result.tables_used}
              latencyMs={result.latency_ms}
              provider={result.provider}
              queryMethod={result.query_method}
              arabic={arabicQuestion}
            />
          </>
        ) : null}

        <HistoryPanel questions={history} onPick={run} onClear={clearHistory} busy={busy} arabic={arabicQuestion} />
      </main>
      <footer dir={arabicQuestion ? "rtl" : "ltr"} className="border-t border-rule">
        <div className="mx-auto max-w-[88rem] px-5 py-6 sm:px-8 lg:px-12">
          <p className="text-[0.9375rem] text-sand">
            {arabicQuestion
              ? "نسخة بيانات مصدّرة من ADREC. نموذج مستقل؛ ليس خدمة رسمية من ADREC."
              : "Source-backed ADREC export snapshot. Independent prototype; not an official ADREC service."}
          </p>
        </div>
      </footer>
    </>
  );
}
