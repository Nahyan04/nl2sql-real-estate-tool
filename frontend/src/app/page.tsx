"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { DataSurface } from "@/components/data-surface";
import { ExampleQuestions } from "@/components/example-questions";
import { PipelineTrace } from "@/components/pipeline-trace";
import { QueryInput } from "@/components/query-input";
import { Wordmark } from "@/components/wordmark";
import { ApiError, getExamples, getSchema, postQuery } from "@/lib/api";
import type { ExampleQuestion, QueryResponse, SchemaTable } from "@/lib/types";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [examples, setExamples] = useState<ExampleQuestion[]>([]);
  const [tables, setTables] = useState<SchemaTable[]>([]);
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

  const run = useCallback(async (text: string) => {
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

    try {
      setResult(await postQuery({ question: asked }, controller.signal));
    } catch (cause) {
      if (cause instanceof Error && cause.name === "AbortError") return;
      setError(cause instanceof ApiError ? cause : new ApiError("UPSTREAM_ERROR", String(cause), 0));
    } finally {
      if (pending.current === controller) setBusy(false);
    }
  }, []);

  const showTrace = busy || result !== null;

  return (
    <>
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-[68rem] items-center justify-between px-8 py-5">
          <Wordmark />
          <p className="hidden text-end text-[0.8125rem] text-sand sm:block">
            Natural-language analytics for Abu Dhabi&rsquo;s real estate market
          </p>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[68rem] flex-1 px-8 pt-16 pb-24">
        <QueryInput value={question} onChange={setQuestion} onSubmit={() => run(question)} busy={busy} />

        {showTrace ? (
          <div className="mt-10">
            <PipelineTrace
              key={runId}
              state={busy ? "running" : "done"}
              attempts={(result?.retry_count ?? 0) + 1}
            />
          </div>
        ) : (
          <>
            <ExampleQuestions examples={examples} onPick={run} busy={busy} />
            <DataSurface tables={tables} />
          </>
        )}

        {error ? (
          <section className="mt-12 border-s-2 border-destructive ps-5">
            <h2 className="label-mono text-destructive">{error.code.replace(/_/g, " ")}</h2>
            <p className="mt-2 text-[0.9375rem] leading-relaxed text-sand">{error.detail}</p>
          </section>
        ) : null}

        {result ? (
          <section className="mt-12">
            <h2 className="label-mono">Answer</h2>
            <p dir="auto" className="mt-3 max-w-[42rem] text-[1.0625rem] leading-relaxed text-limestone">
              {result.answer}
            </p>
          </section>
        ) : null}
      </main>
    </>
  );
}
