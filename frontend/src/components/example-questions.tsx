"use client";

import { useMemo, useState } from "react";

import type { ExampleQuestion, Lang } from "@/lib/types";

const COLLAPSED_COUNT = 5;

interface ExampleQuestionsProps {
  examples: ExampleQuestion[];
  onPick: (question: string) => void;
  busy: boolean;
}

export function ExampleQuestions({ examples, onPick, busy }: ExampleQuestionsProps) {
  const [lang, setLang] = useState<Lang>("en");
  const [expanded, setExpanded] = useState(false);

  const pool = useMemo(() => examples.filter((example) => example.lang === lang), [examples, lang]);
  const visible = expanded ? pool : pool.slice(0, COLLAPSED_COUNT);

  if (examples.length === 0) return null;

  return (
    <section className="mt-10">
      <div className="flex items-baseline justify-between">
        <h2 className="label-mono">Try</h2>
        <div className="flex items-center gap-3">
          {(["en", "ar"] as const).map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => {
                setLang(code);
                setExpanded(false);
              }}
              className={`label-mono cursor-pointer transition-colors ${
                lang === code ? "text-teak" : "text-sand/50 hover:text-sand"
              }`}
            >
              {code}
            </button>
          ))}
        </div>
      </div>

      <ul className="mt-4" dir={lang === "ar" ? "rtl" : "ltr"}>
        {visible.map((example) => (
          <li key={example.id}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onPick(example.text)}
              className="group/q flex w-full cursor-pointer items-baseline gap-2 py-[0.4375rem] text-start text-[0.9375rem] leading-snug text-sand transition-colors hover:text-limestone disabled:cursor-default disabled:hover:text-sand"
            >
              <span
                aria-hidden
                className="w-3 shrink-0 text-teak opacity-0 transition-opacity group-hover/q:opacity-100 rtl:rotate-180"
              >
                →
              </span>
              <span>{example.text}</span>
            </button>
          </li>
        ))}
      </ul>

      {pool.length > COLLAPSED_COUNT ? (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="label-mono mt-2 ms-5 cursor-pointer text-sand/60 transition-colors hover:text-teak"
        >
          {expanded ? "Show fewer" : `Show all ${pool.length}`}
        </button>
      ) : null}
    </section>
  );
}
