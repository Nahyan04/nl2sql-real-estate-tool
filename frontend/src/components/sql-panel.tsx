"use client";

import { useState } from "react";

import { tokenizeSql, type TokenKind } from "@/lib/sql-tokens";

const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword: "text-sage",
  function: "text-ink",
  string: "text-[#8f4526]",
  number: "text-[#2a5d86]",
  comment: "text-sand italic",
  plain: "text-ink/85",
};

interface SqlPanelProps {
  sql: string;
  tablesUsed: string[];
  latencyMs: number;
  provider: string;
  queryMethod?: string;
  arabic?: boolean;
}

function formatLatency(ms: number, arabic: boolean): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} ${arabic ? "ث" : "s"}` : `${ms} ${arabic ? "مللي ثانية" : "ms"}`;
}

export function SqlPanel({ sql, tablesUsed, latencyMs, provider, queryMethod, arabic = false }: SqlPanelProps) {
  if (!sql) return null;

  const sourcePlan = queryMethod?.startsWith("source_plan:");
  const providerLabel = provider === "anthropic"
    ? (arabic ? "خدمة سحابية" : "Cloud API")
    : provider === "ollama" ? (arabic ? "استضافة ذاتية" : "Self-hosted") : provider;

  return (
    <details dir={arabic ? "rtl" : "ltr"} className="group mt-12 border-t border-rule">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline justify-between gap-x-6 gap-y-2 py-4 [&::-webkit-details-marker]:hidden">
        <span className="section-heading flex items-baseline gap-2">
          <span aria-hidden className="text-sage transition-transform group-open:rotate-90">
            ›
          </span>
          {arabic ? "كيف أُعدّت الإجابة" : "How this was answered"}
        </span>
        <span className="label-mono text-sand">
          {sourcePlan ? `${arabic ? "خطة استعلام موثقة" : "Verified query plan"} · ${formatLatency(latencyMs, arabic)}` : (
            <>{providerLabel} · {formatLatency(latencyMs, arabic)}</>
          )}
        </span>
      </summary>

      <div className="pb-2">
        {tablesUsed.length > 0 ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 pb-4">
            <span className="label-mono text-sand">{arabic ? "الجداول المستخدمة" : "Tables used"}</span>
            <span className="font-mono text-[0.9375rem] text-sand">
              {tablesUsed.join("  ·  ")}
            </span>
          </div>
        ) : null}

        <div className="rounded-lg border border-rule bg-paper">
          <div className="flex justify-end border-b border-rule px-3 py-2">
            <CopyButton sql={sql} arabic={arabic} />
          </div>
          <pre dir="ltr" className="overflow-x-auto px-5 py-4 font-mono text-[0.9375rem] leading-[1.7]">
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

function CopyButton({ sql, arabic }: { sql: string; arabic: boolean }) {
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
      className="control-option cursor-pointer rounded-sm px-2 py-1 text-sand transition-colors hover:bg-paper-flat hover:text-sage"
    >
      {copied ? (arabic ? "نُسخ" : "Copied") : (arabic ? "نسخ" : "Copy")}
    </button>
  );
}
