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
  retryCount: number;
  latencyMs: number;
  provider: string;
  queryMethod?: string;
  arabic?: boolean;
}

function formatLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

export function SqlPanel({ sql, tablesUsed, retryCount, latencyMs, provider, queryMethod, arabic = false }: SqlPanelProps) {
  if (!sql) return null;

  const attempts = retryCount + 1;
  const sourcePlan = queryMethod?.startsWith("source_plan:");

  return (
    <details dir={arabic ? "rtl" : "ltr"} className="group mt-12 border-t border-rule">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-6 py-4 [&::-webkit-details-marker]:hidden">
        <span className="label-mono flex items-baseline gap-2 text-ink">
          <span aria-hidden className="text-sage transition-transform group-open:rotate-90">
            ›
          </span>
          {arabic ? "كيف أُعدّت الإجابة" : "How this was answered"}
        </span>
        <span className="label-mono text-sand">
          {sourcePlan ? `${arabic ? "خطة إيجارات موثقة" : "Verified rental plan"} · ${formatLatency(latencyMs)}` : (
            <>{provider} · {formatLatency(latencyMs)} · {arabic ? `${attempts} محاولة` : attempts === 1 ? "1 attempt" : `${attempts} attempts`}</>
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

        <div className="relative rounded-lg border border-rule bg-paper">
          <CopyButton sql={sql} />
          <pre className="overflow-x-auto px-5 py-4 font-mono text-[0.9375rem] leading-[1.7]">
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
      className="label-mono absolute end-3 top-3 cursor-pointer bg-paper px-2 py-1 text-sand transition-colors hover:text-sage"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
