"use client";

import { useEffect, useState } from "react";

interface ProcessOverviewProps {
  startedAt: number;
  arabic: boolean;
}

export function ProcessOverview({ startedAt, arabic }: ProcessOverviewProps) {
  const [now, setNow] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setNow(performance.now()), 200);
    return () => clearInterval(timer);
  }, []);

  const elapsed = Math.max(0, (now - startedAt) / 1000);

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="mt-8 flex items-center gap-3 border-s-2 border-sage bg-paper-flat px-4 py-3" aria-label={arabic ? "حالة التحليل" : "Analysis status"}>
      <span className="size-2 shrink-0 animate-pulse rounded-full bg-sage" aria-hidden />
      <p className="text-[1rem] font-medium text-ink">{arabic ? "جارٍ تحليل السؤال" : "Analyzing your question"}</p>
      <p className="ms-auto font-mono text-sm tabular-nums text-sand" role="timer" aria-live="off">
        {elapsed.toFixed(1)} {arabic ? "ث" : "s"}
      </p>
    </section>
  );
}
