"use client";

import { useEffect, useState } from "react";

/** The graph's own nodes, with synthesize_answer + build_chart folded into one
 *  visible step. Dwell times are an indicator only — the API answers once. */
const STAGES = [
  { key: "retrieve_schema", label: "Retrieve", dwell: 300 },
  { key: "generate_sql", label: "Generate", dwell: 1900 },
  { key: "validate_sql", label: "Validate", dwell: 260 },
  { key: "execute_sql", label: "Execute", dwell: 950 },
  { key: "synthesize_answer", label: "Answer", dwell: 1700 },
] as const;

const LAST = STAGES.length - 1;

export type TraceState = "running" | "done";

/** Mount fresh per query (the parent keys it on the run) so the clock always
 *  starts at the first stage. */
export function PipelineTrace({ state, attempts }: { state: TraceState; attempts: number }) {
  const [reached, setReached] = useState(0);

  useEffect(() => {
    if (state !== "running") return;
    let stage = 0;
    let timer: ReturnType<typeof setTimeout>;
    const step = () => {
      if (stage >= LAST) return;
      timer = setTimeout(() => {
        stage += 1;
        setReached(stage);
        step();
      }, STAGES[stage].dwell);
    };
    step();
    return () => clearTimeout(timer);
  }, [state]);

  const done = state === "done";
  const index = done ? LAST : reached;

  return (
    <div className="w-full" aria-live="polite" aria-label={`Pipeline stage: ${STAGES[index].label}`}>
      <div className="relative">
        <div className="absolute inset-x-[10%] top-[3px] h-px bg-rule" />
        <div
          className="absolute left-[10%] top-[3px] h-px bg-sage transition-[width] duration-500 ease-out"
          style={{ width: `${(index / LAST) * 80}%` }}
        />
        <ol className="relative flex">
          {STAGES.map((stage, i) => {
            const passed = done || i < index;
            const active = !done && i === index;
            return (
              <li key={stage.key} className="flex flex-1 flex-col items-center gap-2.5">
                <span
                  className={[
                    "size-[7px] rounded-full ring-3 ring-canvas transition-colors duration-300",
                    passed || active ? "bg-sage" : "bg-rule",
                    active ? "animate-pulse" : "",
                  ].join(" ")}
                />
                <span
                  className={[
                    "label-mono transition-colors duration-300",
                    passed || active ? "text-ink" : "text-sand",
                  ].join(" ")}
                >
                  {stage.label}
                </span>
                {stage.key === "generate_sql" && attempts > 1 ? <RetryLoop attempts={attempts} /> : null}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/** Generation ran more than once: validation or execution fed an error back
 *  into the same node. The count is measured, not estimated. */
function RetryLoop({ attempts }: { attempts: number }) {
  return (
    <span className="mt-1 flex items-center gap-1.5 text-sage" title={`Generated ${attempts} times`}>
      <svg width="30" height="14" viewBox="0 0 30 14" fill="none" aria-hidden>
        <path d="M21 2 C29 2 29 11 15 11 C1 11 1 2 9 2" stroke="currentColor" strokeWidth="1" />
        <path d="M9 2 L12 4.5 M9 2 L12 -0.5" stroke="currentColor" strokeWidth="1" />
      </svg>
      <span className="font-mono text-[0.6875rem] tracking-wide">×{attempts}</span>
    </span>
  );
}
