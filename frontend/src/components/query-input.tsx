"use client";

import { useEffect, useRef } from "react";

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  providerAvailable: boolean;
  arabic: boolean;
}

export function QueryInput({ value, onChange, onSubmit, busy, providerAvailable, arabic }: QueryInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    };
    fit();
    // a narrower viewport rewraps the question, so the box has to regrow
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [value]);

  const submittable = value.trim().length > 0 && !busy && providerAvailable;

  return (
    <form dir={arabic ? "rtl" : "ltr"}
      className="group"
      onSubmit={(event) => {
        event.preventDefault();
        if (submittable) onSubmit();
      }}
    >
      <label htmlFor="question" className="section-heading">
        {arabic ? "اسأل عن السوق العقاري" : "Ask about the market"}
      </label>
      <div className="mt-3 flex items-start gap-6">
        <textarea
          id="question"
          ref={ref}
          rows={1}
          dir="auto"
          spellCheck={false}
          autoComplete="off"
          disabled={busy}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (submittable) onSubmit();
            }
          }}
          placeholder={arabic ? "اسأل عن المبيعات أو الإيجارات أو مؤشرات الأسعار" : "Ask about sales, rental observations or price indices"}
          className="query-field min-w-0 flex-1 resize-none bg-transparent text-[1.5rem] font-medium leading-[1.55] text-ink placeholder:text-sand/70 focus-visible:outline-none disabled:text-sand"
        />
        <button
          type="submit"
          disabled={!submittable}
          className="label-mono mt-2 shrink-0 cursor-pointer text-sage transition-opacity hover:opacity-70 disabled:cursor-default disabled:text-sand/40 disabled:hover:opacity-100"
        >
          {busy ? (arabic ? "جارٍ التحليل" : "Working") : (arabic ? "اسأل ↵" : "Ask ↵")}
        </button>
      </div>
      <div
        className={[
          "mt-3 transition-colors duration-200",
          busy ? "h-px bg-sage-dim" : "h-px bg-rule group-focus-within:bg-sage",
        ].join(" ")}
      />
      {!providerAvailable ? <p className="mt-3 text-sm text-sand" role="status">{arabic ? "اختر خدمة نموذج متاحة قبل إرسال السؤال." : "Choose an available model provider before asking."}</p> : null}
    </form>
  );
}
