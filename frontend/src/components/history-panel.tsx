"use client";

export function HistoryPanel({ questions, onPick, onClear, busy, arabic }: {
  questions: string[]; onPick: (question: string) => void; onClear: () => void; busy: boolean; arabic: boolean;
}) {
  if (!questions.length) return null;
  return (
    <details dir={arabic ? "rtl" : "ltr"} className="mt-10 border-t border-rule pt-4">
      <summary className="min-h-11 cursor-pointer text-sm font-semibold text-sand transition-colors hover:text-ink">
        {arabic ? "أسئلة هذه الجلسة" : "Session history"} <span className="ms-2 font-mono text-xs font-normal">{questions.length}</span>
      </summary>
      <div className="mt-2 rounded-lg bg-paper-flat px-5 py-3">
        <ul className="divide-y divide-rule">
          {questions.map((question) => <li key={question}><button type="button" disabled={busy} dir="auto" onClick={() => onPick(question)} className="w-full cursor-pointer py-3 text-start text-sm leading-relaxed text-sand transition-colors hover:text-sage disabled:cursor-default disabled:opacity-50">{question}</button></li>)}
        </ul>
        <button type="button" onClick={onClear} className="min-h-11 cursor-pointer text-sm font-semibold text-sand underline decoration-rule underline-offset-4 hover:text-ink">{arabic ? "مسح السجل" : "Clear history"}</button>
      </div>
    </details>
  );
}
