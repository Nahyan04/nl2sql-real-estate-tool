"use client";

import { useState } from "react";

import { tokenizeSql, type TokenKind } from "@/lib/sql-tokens";

const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword: "text-teak",
  function: "text-limestone",
  string: "text-[#9bb394]",
  number: "text-[#cdbb8b]",
  comment: "text-sand/60 italic",
  plain: "text-limestone/85",
};

interface SqlPanelProps {
  sql: string;
  tablesUsed: string[];
  retryCount: number;
  latencyMs: number;
  provider: string;
}

function formatLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

export function SqlPanel({ sql, tablesUsed, retryCount, latencyMs, provider }: SqlPanelProps) {
  if (!sql) return null;

  const attempts = retryCount + 1;

  return (
    <details className="group mt-12 border-t border-rule">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-6 py-4 [&::-webkit-details-marker]:hidden">
        <span className="label-mono flex items-baseline gap-2 text-limestone">
          <span aria-hidden className="text-teak transition-transform group-open:rotate-90">
            ›
          </span>
          How this was answered
        </span>
        <span className="label-mono text-sand/70">
          {provider} · {formatLatency(latencyMs)} ·{" "}
          {attempts === 1 ? "1 attempt" : `${attempts} attempts`}
        </span>
      </summary>

      <div className="pb-2">
        {tablesUsed.length > 0 ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 pb-4">
            {/* the retrieval shortlist, not the tables the query touched */}
            <span className="label-mono text-sand/60">Tables considered</span>
            <span className="font-mono text-[0.8125rem] text-sand">
              {tablesUsed.join("  ·  ")}
            </span>
          </div>
        ) : null}

        <div className="relative rounded-lg border border-rule bg-ledger">
          <CopyButton sql={sql} />
          <pre className="overflow-x-auto px-5 py-4 font-mono text-[0.8125rem] leading-[1.7]">
            <code>
              {tokenizeSql(sql).map((token, index) => (
                <span key={index} className={TOKEN_CLASS[token.kind]}>
                  {token.text}
                </span>
              ))}
            </code>
          </pre>
        </div>
      </div>
    </details>
  );
}

function CopyButton({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(sql).then(
          () => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          },
          () => setCopied(false),
        );
      }}
      className="label-mono absolute end-3 top-3 cursor-pointer bg-ledger px-2 py-1 text-sand/70 transition-colors hover:text-teak"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
