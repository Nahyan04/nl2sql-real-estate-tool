"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Header } from "@/components/header";
import { SiteFooter } from "@/components/site-footer";
import { getSchema } from "@/lib/api";
import { DATA_TOPICS, displayDate, topicCoverage } from "@/lib/data-topics";
import type { LanguageChoice, SchemaResponse } from "@/lib/types";

export function DataGuide({ initialArabic }: { initialArabic: boolean }) {
  const [language, setLanguage] = useState<LanguageChoice>(initialArabic ? "ar" : "en");
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const arabic = language === "ar";
  useEffect(() => {
    const controller = new AbortController();
    getSchema(controller.signal).then((response) => { setSchema(response); setFailed(false); }).catch((cause) => { if (cause.name !== "AbortError") setFailed(true); });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => { document.documentElement.lang = arabic ? "ar" : "en"; }, [arabic]);
  const names = new Set(schema?.tables.map((table) => table.name));
  const sales = schema?.coverage.find((source) => source.source_file === DATA_TOPICS[0].files[0]);
  return <>
    <Header page="data" language={language} arabic={arabic} onLanguageChange={setLanguage} busy={false} />
    <main id="main-content" dir={arabic ? "rtl" : "ltr"} className="mx-auto w-full max-w-[88rem] flex-1 px-5 py-10 sm:px-8 lg:px-12 lg:py-14">
      <div className="mt-3 grid items-end gap-7 lg:grid-cols-[minmax(0,1.5fr)_minmax(16rem,0.6fr)]">
        <div>
          <h1 className="display-heading max-w-[23ch]">{arabic ? "من نشاط المبيعات إلى اتجاهات السوق." : "From sales activity to market trends."}</h1>
          <p className="mt-5 max-w-[60ch] text-lg leading-relaxed text-sand">{arabic ? "يحلل بيان بيانات ADREC المصدّرة ليجيب عن أسئلة عملية حول سوق أبوظبي العقاري. تعرف على الموضوعات والمقاييس التي يمكنك استكشافها." : "Bayan analyzes exported ADREC data to answer practical questions about Abu Dhabi real estate. Explore the subjects and measures you can ask about."}</p>
        </div>
        <dl className="border-s-2 border-sage/35 ps-5">
          <dt className="text-sm text-sand">{arabic ? "نسخة البيانات" : "Data snapshot"}</dt>
          <dd dir="ltr" className="mt-1 font-mono text-xl font-semibold text-ink">{schema?.snapshot_id ?? "—"}</dd>
          {sales?.source_rows !== undefined ? <><dt className="mt-5 text-sm text-sand">{arabic ? "سجلات مبيعات مصدّرة" : "Exported sales observations"}</dt><dd className="mt-1 font-mono text-2xl font-semibold tabular-nums text-ink">{sales.source_rows.toLocaleString("en-GB")}</dd></> : null}
        </dl>
      </div>
      {failed ? <div className="mt-8 rounded-xl border border-rule bg-paper-flat p-5" role="status"><p className="text-sand">{arabic ? "تعذر تحميل تفاصيل النسخة حاليًا." : "Snapshot details could not be loaded."}</p><button className="mt-2 min-h-11 cursor-pointer font-semibold text-sage" onClick={() => setAttempt((value) => value + 1)}>{arabic ? "حاول مرة أخرى" : "Try again"}</button></div> : null}
      <div className="mt-10 space-y-5">
        {DATA_TOPICS.filter((topic) => !schema || names.has(topic.table)).map((topic, index) => {
          const copy = arabic ? topic.ar : topic.en;
          const dates = topicCoverage(schema?.coverage ?? [], topic.files);
          return <section key={topic.id} className="grid gap-6 rounded-2xl border border-rule bg-paper-flat p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12">
            <div>
              <p className="font-mono text-xs text-sage" aria-hidden>0{index + 1}</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-ink">{copy.title}</h2>
              <p className="mt-3 max-w-[52ch] text-base leading-relaxed text-sand">{copy.description}</p>
              <Link href={`/?${new URLSearchParams({ question: copy.question, ...(arabic ? { lang: "ar" } : {}) })}`} className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-sage hover:underline underline-offset-4">{arabic ? "جرّب سؤالًا عن هذا الموضوع" : "Try a question about this data"}<ArrowUpRight className="size-4 rtl:-scale-x-100" aria-hidden /></Link>
            </div>
            <dl className="grid gap-5 border-t border-rule pt-5 lg:border-s lg:border-t-0 lg:ps-7 lg:pt-0">
              <div><dt className="text-xs font-semibold text-sage">{arabic ? "المقاييس الرئيسية" : "Main measures"}</dt><dd className="mt-1.5 text-base leading-relaxed text-ink">{copy.measures}</dd></div>
              <div className="grid gap-5 sm:grid-cols-2"><div><dt className="text-xs font-semibold text-sage">{arabic ? "التواريخ المتاحة في النسخة" : "Observed dates in snapshot"}</dt><dd className="mt-1.5 text-sm leading-relaxed text-ink">{dates.from && dates.through ? `${displayDate(dates.from, arabic)} – ${displayDate(dates.through, arabic)}` : (failed ? (arabic ? "غير متاحة حاليًا" : "Currently unavailable") : (arabic ? "جارٍ تحميل التواريخ…" : "Loading dates…"))}</dd></div><div><dt className="text-xs font-semibold text-sage">{arabic ? "الوحدات" : "Units"}</dt><dd className="mt-1.5 text-sm text-ink">{copy.units}</dd></div></div>
              <div><dt className="text-xs font-semibold text-sage">{arabic ? "مستوى البيانات" : "Data detail"}</dt><dd className="mt-1.5 text-sm text-sand">{copy.grain}</dd></div>
            </dl>
          </section>;
        })}
      </div>
      <Link href={`/${arabic ? "?lang=ar" : ""}`} className="ask-button mt-8">{arabic ? "اسأل بيان" : "Ask Bayan"}<ArrowUpRight className="size-4 rtl:-scale-x-100" aria-hidden /></Link>
    </main>
    <SiteFooter arabic={arabic} />
  </>;
}
