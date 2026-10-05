"use client";

import { useEffect, useRef } from "react";
import { ArrowUpRight } from "lucide-react";

export function QueryInput({ value, onChange, onSubmit, busy, providerAvailable, providerLoading = false, arabic }: {
  value: string; onChange: (value: string) => void; onSubmit: () => void; busy: boolean;
  providerAvailable: boolean; providerLoading?: boolean; arabic: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => { el.style.height = "auto"; el.style.height = `${el.scrollHeight}px`; };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [value]);
  const submittable = value.trim().length > 0 && !busy && providerAvailable;
  return (
    <form dir={arabic ? "rtl" : "ltr"} className="composer" onSubmit={(event) => { event.preventDefault(); if (submittable) onSubmit(); }}>
      <label htmlFor="question" className="sr-only">{arabic ? "سؤالك" : "Your question"}</label>
      <textarea id="question" ref={ref} rows={1} dir={arabic ? "rtl" : "ltr"} spellCheck={false} autoComplete="off" disabled={busy} value={value} maxLength={1000}
        onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (submittable) onSubmit(); }
        }}
        placeholder={arabic ? "اسأل عن المبيعات أو الإيجارات أو اتجاهات السوق…" : "Ask about sales, leasing, or market trends…"}
        className="query-field block min-h-10 w-full resize-none rounded-md bg-transparent text-lg font-normal leading-relaxed text-start text-ink placeholder:text-sand/65 focus-visible:outline-offset-4 disabled:text-sand sm:text-xl" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-4 border-t border-rule pt-4">
        <p className="text-xs leading-relaxed text-sand">{arabic ? "Enter لإرسال السؤال · Shift + Enter لسطر جديد" : "Enter to ask · Shift + Enter for a new line"}</p>
        <button type="submit" disabled={!submittable} className="ask-button">
          {busy ? (arabic ? "جارٍ التحليل" : "Analyzing") : (arabic ? "اسأل بيان" : "Ask Bayan")}
          <ArrowUpRight className="size-4 rtl:-scale-x-100" aria-hidden />
        </button>
      </div>
      {!providerAvailable && !providerLoading ? <p className="mt-3 text-sm text-sand" role="status">{arabic ? "خدمة التحليل غير متاحة حاليًا. حاول مرة أخرى بعد قليل." : "Analysis is currently unavailable. Please try again shortly."}</p> : null}
    </form>
  );
}
