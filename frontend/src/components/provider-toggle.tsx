"use client";

import type { Provider } from "@/lib/types";

const OPTIONS: { value: Provider; label: string; hint: string }[] = [
  { value: "anthropic", label: "Hosted", hint: "Runs against a hosted model" },
  { value: "ollama", label: "On-prem", hint: "Runs against a local model — no data leaves the environment" },
];

interface ProviderToggleProps {
  value: Provider;
  onChange: (provider: Provider) => void;
  disabled: boolean;
}

export function ProviderToggle({ value, onChange, disabled }: ProviderToggleProps) {
  return (
    <div className="flex shrink-0 items-baseline gap-3">
      <span className="label-mono text-sand/60">Model</span>
      <div className="flex items-baseline gap-2">
        {OPTIONS.map((option, index) => (
          <span key={option.value} className="flex items-baseline gap-2">
            {index > 0 ? (
              <span aria-hidden className="text-sand/30">
                ·
              </span>
            ) : null}
            <button
              type="button"
              title={option.hint}
              disabled={disabled}
              aria-pressed={value === option.value}
              onClick={() => onChange(option.value)}
              className={`label-mono cursor-pointer transition-colors disabled:cursor-default ${
                value === option.value ? "text-teak" : "text-sand/50 hover:text-sand"
              }`}
            >
              {option.label}
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
