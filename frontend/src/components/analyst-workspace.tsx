"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { AnswerPanel } from "@/components/answer-panel";
import { SiteFooter } from "@/components/site-footer";
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
import { ApiError, getExamples, getProviders, getSchema, postQuery } from "@/lib/api";
import { resolveLanguage } from "@/lib/language";
import { clearHistory, getHistory, getServerHistory, pushHistory, subscribeHistory } from "@/lib/history";
import type { ExampleQuestion, Lang, LanguageChoice, Provider, ProvidersResponse, QueryResponse, SchemaTable, SourceCoverage } from "@/lib/types";

export function AnalystWorkspace({ initialQuestion = "", initialLanguage = "auto" }: { initialQuestion?: string; initialLanguage?: LanguageChoice }) {
  const [question, setQuestion] = useState(initialQuestion);
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [availabilityFailed, setAvailabilityFailed] = useState(false);
  const [availability, setAvailability] = useState<ProvidersResponse | null>(null);
  const [languageChoice, setLanguageChoice] = useState<LanguageChoice>(initialLanguage);
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
    getProviders(controller.signal)
      .then(setAvailability)
      .catch(() => setAvailabilityFailed(true));
    return () => controller.abort();
  }, []);

  const run = useCallback(
    async (text: string) => {
      const asked = text.trim();
      if (!asked || availability?.[provider].available !== true) return;
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
    [provider, languageChoice, availability],
  );

  const clearCurrent = useCallback(() => {
    pending.current?.abort();
    pending.current = null;
    setQuestion("");
    setResult(null);
    setError(null);
    setBusy(false);
    setRunId((id) => id + 1);
    requestAnimationFrame(() => document.getElementById("question")?.focus());
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
  const providerAvailable = availability?.[provider].available === true;

  useEffect(() => {
    document.documentElement.lang = arabicQuestion ? "ar" : "en";
  }, [arabicQuestion]);

  return (
    <>
      <Header provider={provider} language={languageChoice} arabic={arabicQuestion} onLanguageChange={changeLanguage} onProviderChange={setProvider} busy={busy} availability={availability} availabilityFailed={availabilityFailed} />

      <main id="main-content" dir={arabicQuestion ? "rtl" : "ltr"} className="mx-auto w-full max-w-[88rem] flex-1 px-5 pt-8 pb-16 sm:px-8 lg:px-12 lg:pt-12">
        {!showProcess ? <div className="mb-8 grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_24rem] lg:gap-10">
          <div>
            <h1 className="display-heading max-w-[22ch]">{arabicQuestion ? "اسأل عن سوق أبوظبي العقاري." : "Ask about Abu Dhabi real estate."}</h1>
            <p className="mt-4 max-w-[54ch] text-base leading-relaxed text-sand sm:text-lg">{arabicQuestion ? "إجابات ورسوم بيانية وأدلة من المصادر، بالعربية أو الإنجليزية." : "Answers, charts, and source evidence. In English or Arabic."}</p>
          </div>
          <div className="hidden lg:block"><DataSurface tables={tables} arabic={arabicQuestion} /></div>
        </div> : null}
        <QueryInput value={question} onChange={setQuestion} onSubmit={() => run(question)} busy={busy} providerAvailable={providerAvailable} providerLoading={availability === null && !availabilityFailed} arabic={arabicQuestion} />
        {showProcess ? (
          <button type="button" onClick={clearCurrent}
            className="mt-3 min-h-11 cursor-pointer rounded-md px-1 text-sm font-semibold text-sage transition-colors hover:text-ink">
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
          <ExampleQuestions key={arabicQuestion ? "ar" : "en"} examples={examples} onPick={run} busy={busy || !providerAvailable} arabic={arabicQuestion} />
        ) : null}

        {error ? <ErrorPanel error={error} arabic={arabicQuestion} onRetry={() => run(question)} /> : null}

        {result ? (
          <>
            <div className="mt-7 grid items-start gap-7 xl:grid-cols-[minmax(0,1.85fr)_minmax(17rem,0.8fr)]">
              <article className="min-w-0 rounded-2xl bg-paper-flat p-5 sm:p-7">
              <AnswerPanel answer={result.answer} arabic={arabicQuestion} title={result.outcome === "no_data"
                ? (arabicQuestion ? "لا توجد بيانات مطابقة" : "No matching data")
                : (arabicQuestion ? "النتيجة الرئيسية" : "Key finding")} />
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
              </article>
              <aside className="min-w-0 xl:sticky xl:top-8"><EvidencePanel result={result} coverage={coverage} schemaSnapshotId={schemaSnapshotId} arabic={arabicQuestion} /></aside>
            </div>
          </>
        ) : null}

        <HistoryPanel questions={history} onPick={run} onClear={clearHistory} busy={busy || !providerAvailable} arabic={arabicQuestion} />
      </main>
      <SiteFooter arabic={arabicQuestion} />
    </>
  );
}
