"use client";

import { useEffect, useState } from "react";

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
  const [expanded, setExpanded] = useState(false);
  const [formatted, setFormatted] = useState<{ source: string; text: string } | null>(null);
  useEffect(() => {
    if (!expanded || !sql) return;
    let current = true;
    // Format only the display; execution and copying retain the original SQL.
    import("sql-formatter").then(({ format }) => {
      const text = format(sql, { language: "postgresql", tabWidth: 2, keywordCase: "upper" });
      if (current) setFormatted({ source: sql, text });
    }).catch(() => { if (current) setFormatted({ source: sql, text: sql }); });
    return () => { current = false; };
  }, [expanded, sql]);
  if (!sql) return null;
  const displaySql = formatted?.source === sql ? formatted.text : sql;

  const sourcePlan = queryMethod?.startsWith("source_plan:");
  const providerLabel = provider === "anthropic"
    ? (arabic ? "خدمة سحابية" : "Cloud API")
    : provider === "ollama" ? (arabic ? "استضافة ذاتية" : "Self-hosted") : provider;

  return (
    <details dir={arabic ? "rtl" : "ltr"} onToggle={(event) => setExpanded(event.currentTarget.open)} className="group mt-12 border-t border-rule">
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
            <span className="font-mono text-sm text-sand">
              {tablesUsed.join("  ·  ")}
            </span>
          </div>
        ) : null}

        <div className="rounded-lg border border-rule bg-paper">
          <div className="flex items-center justify-between gap-4 border-b border-rule px-5 py-3">
            <span className="text-sm font-medium text-ink">{arabic ? "استعلام SQL المنفذ" : "Executed SQL"}</span>
            <CopyButton sql={sql} arabic={arabic} />
          </div>
          <pre dir="ltr" className="whitespace-pre-wrap break-words px-5 py-6 font-mono text-sm leading-relaxed [overflow-wrap:anywhere] sm:px-6 sm:text-base">
            <code>
              {tokenizeSql(displaySql).map((token, index) => (
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
