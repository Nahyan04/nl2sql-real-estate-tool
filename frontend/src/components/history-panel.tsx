"use client";

interface HistoryPanelProps {
  questions: string[];
  onPick: (question: string) => void;
  onClear: () => void;
  busy: boolean;
  arabic: boolean;
}

export function HistoryPanel({ questions, onPick, onClear, busy, arabic }: HistoryPanelProps) {
  if (questions.length === 0) return null;

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="mt-16 border-t border-rule pt-5">
      <div className="flex items-baseline justify-between gap-6">
        <h2 className="section-heading">{arabic ? "أسئلة هذه الجلسة" : "This session"}</h2>
        <button
          type="button"
          onClick={onClear}
          className="label-mono cursor-pointer text-sand transition-colors hover:text-sage"
        >
          {arabic ? "مسح السجل" : "Clear"}
        </button>
      </div>
      <ul className="mt-3">
        {questions.map((question) => (
          <li key={question}>
            <button
              type="button"
              disabled={busy}
              dir="auto"
              onClick={() => onPick(question)}
              className="w-full cursor-pointer py-[0.3125rem] text-start text-[1rem] font-medium leading-snug text-sand transition-colors hover:text-ink disabled:cursor-default disabled:hover:text-sand"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
