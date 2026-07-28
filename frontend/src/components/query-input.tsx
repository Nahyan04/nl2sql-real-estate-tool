"use client";

import { useEffect, useRef } from "react";

interface QueryInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
}

export function QueryInput({ value, onChange, onSubmit, busy }: QueryInputProps) {
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

  const submittable = value.trim().length > 0 && !busy;

  return (
    <form
      className="group"
      onSubmit={(event) => {
        event.preventDefault();
        if (submittable) onSubmit();
      }}
    >
      <label htmlFor="question" className="label-mono">
        Ask
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
          placeholder="Ask about transactions, rents, mortgages or price indices"
          className="min-w-0 flex-1 resize-none bg-transparent text-[1.5rem] font-medium leading-[1.45] text-ink placeholder:text-sand/70 focus-visible:outline-none disabled:text-sand"
        />
        <button
          type="submit"
          disabled={!submittable}
          className="label-mono mt-2 shrink-0 cursor-pointer text-sage transition-opacity hover:opacity-70 disabled:cursor-default disabled:text-sand/40 disabled:hover:opacity-100"
        >
          {busy ? "Working" : "Ask ↵"}
        </button>
      </div>
      <div
        className={[
          "mt-3 transition-colors duration-200",
          busy ? "h-px bg-sage-dim" : "h-px bg-rule group-focus-within:bg-sage",
        ].join(" ")}
      />
    </form>
  );
}
