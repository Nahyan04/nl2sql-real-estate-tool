"use client";

interface HistoryPanelProps {
  questions: string[];
  onPick: (question: string) => void;
  onClear: () => void;
  busy: boolean;
}

export function HistoryPanel({ questions, onPick, onClear, busy }: HistoryPanelProps) {
  if (questions.length === 0) return null;

  return (
    <section className="mt-16 border-t border-rule pt-5">
      <div className="flex items-baseline justify-between gap-6">
        <h2 className="label-mono">This session</h2>
        <button
          type="button"
          onClick={onClear}
          className="label-mono cursor-pointer text-sand/50 transition-colors hover:text-teak"
        >
          Clear
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
              className="w-full cursor-pointer py-[0.3125rem] text-start text-[0.875rem] leading-snug text-sand transition-colors hover:text-limestone disabled:cursor-default disabled:hover:text-sand"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
