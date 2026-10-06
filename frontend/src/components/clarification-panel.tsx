"use client";

import { useEffect, useRef, useState } from "react";
import type { ClarificationAnswer, ClarificationQuestion } from "@/lib/types";

export function ClarificationPanel({ questions, arabic, onContinue, onCancel }: {
  questions: ClarificationQuestion[];
  arabic: boolean;
  onContinue: (answers: ClarificationAnswer[]) => void;
  onCancel: () => void;
}) {
  const [selected, setSelected] = useState<Record<string, string>>({});
  const panel = useRef<HTMLElement>(null);
  const ready = questions.every((question) => selected[question.id]);
  useEffect(() => { panel.current?.focus(); }, []);

  return (
    <section ref={panel} tabIndex={-1} dir={arabic ? "rtl" : "ltr"} aria-labelledby="clarification-heading" className="mt-6 rounded-2xl border border-rule bg-paper-flat p-5 sm:p-7">
      <h2 id="clarification-heading" className="section-heading">{arabic ? "توضيح سريع" : "A quick clarification"}</h2>
      <p className="mt-2 text-sm text-sand">{arabic ? "اختر النطاق المقصود للمتابعة. نطلب توضيحين كحد أقصى." : "Choose the scope you mean to continue. At most two clarification questions."}</p>
      <form onSubmit={(event) => {
        event.preventDefault();
        if (ready) onContinue(questions.map((question) => ({ question_id: question.id, option_id: selected[question.id] })));
      }}>
        <div className="mt-5 space-y-5">
          {questions.map((question) => (
            <fieldset key={question.id}>
              <legend className="text-base font-semibold text-ink">{question.prompt}</legend>
              <div className="mt-3 flex flex-wrap gap-2">
                {question.options.map((option) => (
                  <label key={option.id} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-sage ${selected[question.id] === option.id ? "border-sage bg-sage/10 text-ink" : "border-rule text-sand hover:border-sage"}`}>
                    <input type="radio" name={question.id} value={option.id} checked={selected[question.id] === option.id}
                      onChange={() => setSelected((previous) => ({ ...previous, [question.id]: option.id }))} className="accent-sage" />
                    <span dir="auto">{option.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button type="submit" disabled={!ready} className="min-h-11 cursor-pointer rounded-lg bg-sage px-5 py-2 text-sm font-semibold text-paper disabled:cursor-not-allowed disabled:opacity-40">{arabic ? "متابعة التحليل" : "Continue analysis"}</button>
          <button type="button" onClick={onCancel} className="min-h-11 cursor-pointer rounded-lg border border-rule px-4 py-2 text-sm text-ink">{arabic ? "تعديل السؤال" : "Edit question"}</button>
        </div>
      </form>
    </section>
  );
}
