"use client";

import { useId, useState } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import type { ExampleQuestion, Lang } from "@/lib/types";

const TOPICS = ["sales", "leasing", "trends"] as const;
const LABELS = {
  en: { sales: "Sales", leasing: "Leasing", trends: "Market trends" },
  ar: { sales: "المبيعات", leasing: "الإيجارات", trends: "اتجاهات السوق" },
};

export function ExampleQuestions({ examples, onPick, busy, arabic }: {
  examples: ExampleQuestion[]; onPick: (question: string) => void; busy: boolean; arabic: boolean;
}) {
  const [lang, setLang] = useState<Lang>(arabic ? "ar" : "en");
  const [expanded, setExpanded] = useState(false);
  const galleryId = useId();
  const pool = examples.filter((example) => example.lang === lang);
  const featured = pool.filter((example) => example.featured).slice(0, 3);
  const starters = featured.length ? featured : pool.slice(0, 3);
  if (!examples.length) return null;

  return (
    <section className="mt-9" aria-labelledby={`${galleryId}-heading`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id={`${galleryId}-heading`} className="section-heading">{arabic ? "ابدأ بسؤال من واقع العمل" : "Start with a real-world question"}</h2>
          <p className="mt-1 text-sm text-sand">{arabic ? "اختر سؤالًا لعرض التحليل." : "Choose a question to run an analysis."}</p>
        </div>
        <div className="flex gap-1" role="group" aria-label={arabic ? "لغة الأمثلة" : "Example language"}>
          {(["en", "ar"] as const).map((code) => <button key={code} type="button" aria-pressed={lang === code} onClick={() => setLang(code)} className={`min-h-10 cursor-pointer rounded-md px-3 text-sm font-semibold transition-colors ${lang === code ? "bg-sage/10 text-sage" : "text-sand hover:bg-paper-flat"}`}>
            {code === "en" ? "English" : "العربية"}
          </button>)}
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3" dir={lang === "ar" ? "rtl" : "ltr"}>
        {starters.map((example) => <button key={example.id} type="button" disabled={busy} onClick={() => onPick(example.text)} className="example-card group text-start">
          <span className="flex items-center justify-between gap-3 text-sm font-semibold text-sage">
            {LABELS[lang][example.topic ?? "sales"]}
            <ArrowUpRight className="size-4 shrink-0 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 rtl:-scale-x-100" aria-hidden />
          </span>
          <span className="mt-4 block text-lg font-semibold leading-snug text-ink">{example.title || example.text}</span>
          {example.title ? <span className="mt-2 block text-sm leading-relaxed text-sand">{example.text}</span> : null}
        </button>)}
      </div>
      <button type="button" aria-expanded={expanded} aria-controls={galleryId} onClick={() => setExpanded((open) => !open)} className="mt-4 inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md px-1 text-sm font-semibold text-sage transition-colors hover:text-ink">
        {expanded ? (arabic ? "إخفاء الأسئلة" : "Close question gallery") : (arabic ? `استكشف جميع الأسئلة (${pool.length})` : `Explore all ${pool.length} questions`)}
        <ChevronDown className={`size-4 transition-transform ${expanded ? "rotate-180" : ""}`} aria-hidden />
      </button>
      <div id={galleryId} hidden={!expanded} dir={lang === "ar" ? "rtl" : "ltr"} className="mt-3 rounded-xl border border-rule bg-paper-flat p-5 sm:p-6">
        <div className="grid gap-7 md:grid-cols-3">
          {TOPICS.map((topic) => <section key={topic}>
            <h3 className="text-sm font-semibold text-sage">{LABELS[lang][topic]}</h3>
            <ul className="mt-3 divide-y divide-rule">
              {pool.filter((example) => (example.topic ?? "sales") === topic).map((example) => <li key={example.id}>
                <button type="button" disabled={busy} onClick={() => onPick(example.text)} className="flex w-full cursor-pointer items-start gap-3 py-3 text-start text-sm leading-relaxed text-ink transition-colors hover:text-sage disabled:cursor-default disabled:opacity-50">
                  <span>{example.text}</span><ArrowUpRight className="mt-1 size-4 shrink-0 rtl:-scale-x-100" aria-hidden />
                </button>
              </li>)}
            </ul>
          </section>)}
        </div>
      </div>
    </section>
  );
}
