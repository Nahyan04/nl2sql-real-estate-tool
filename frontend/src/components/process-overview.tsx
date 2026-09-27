"use client";

import { useEffect, useState } from "react";

const STEPS_EN = [
  { number: "01", title: "Understand", description: "Match the question to available source data." },
  { number: "02", title: "Check", description: "Generate and validate read-only SQL." },
  { number: "03", title: "Read", description: "Run the bounded query on the source snapshot." },
  { number: "04", title: "Explain", description: "Present the answer, data and SQL evidence." },
] as const;
const STEPS_AR = [
  { number: "01", title: "فهم السؤال", description: "مطابقة السؤال مع البيانات المتاحة." },
  { number: "02", title: "التحقق", description: "إنشاء استعلام SQL للقراءة فقط والتحقق منه." },
  { number: "03", title: "قراءة البيانات", description: "تنفيذ استعلام محدود على نسخة البيانات." },
  { number: "04", title: "تفسير النتائج", description: "عرض الإجابة والبيانات واستعلام SQL." },
] as const;

interface ProcessOverviewProps {
  running: boolean;
  failed: boolean;
  startedAt: number;
  finishedAt: number | null;
  arabic: boolean;
}

export function ProcessOverview({ running, failed, startedAt, finishedAt, arabic }: ProcessOverviewProps) {
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(performance.now()), 200);
    return () => clearInterval(timer);
  }, [running]);

  const elapsed = Math.max(0, ((finishedAt ?? now) - startedAt) / 1000);
  const status = arabic
    ? running ? "جارٍ التحليل" : failed ? "توقف" : "اكتمل"
    : running ? "Analyzing" : failed ? "Stopped" : "Complete";
  const steps = arabic ? STEPS_AR : STEPS_EN;

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="mt-10 rounded-xl border border-rule bg-paper-flat px-5 py-5 sm:px-6" aria-label={arabic ? "نظرة عامة على التحليل" : "Analysis process overview"}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-5 gap-y-2">
        <div>
          <h2 className="label-mono text-sage">{arabic ? "من السؤال إلى الدليل" : "From question to evidence"}</h2>
          <p className="mt-1 text-sm leading-relaxed text-sand">
            {arabic ? "تصف الخطوات طريقة التحليل. الوقت المعروض هو زمن انتظار هذا الطلب." : "The steps below describe the analysis. The timer measures this request."}
          </p>
        </div>
        <p className="font-mono text-sm tabular-nums text-ink" role="timer" aria-live="off">
          {status} · {elapsed.toFixed(1)} {arabic ? "ث" : "s"}
        </p>
      </div>
      <ol className="mt-6 grid gap-4 border-t border-rule pt-5 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step) => (
          <li key={step.number} className="flex gap-3">
            <span className="font-mono text-xs font-medium text-sage" aria-hidden>{step.number}</span>
            <div>
              <h3 className="text-sm font-semibold text-ink">{step.title}</h3>
              <p className="mt-1 text-sm leading-snug text-sand">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
