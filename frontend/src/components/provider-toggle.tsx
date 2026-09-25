"use client";

import type { Provider } from "@/lib/types";

const OPTIONS: { value: Provider; label: string; hint: string }[] = [
  { value: "anthropic", label: "Cloud API", hint: "Questions and answer context are sent to the configured cloud model" },
  { value: "ollama", label: "Self-hosted", hint: "Uses the configured Ollama endpoint when it is available" },
];

interface ProviderToggleProps {
  value: Provider;
  onChange: (provider: Provider) => void;
  disabled: boolean;
}

export function ProviderToggle({ value, onChange, disabled }: ProviderToggleProps) {
  return (
    <div className="flex shrink-0 items-baseline gap-3">
      <span className="label-mono text-sand">Model</span>
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
                value === option.value ? "font-medium text-sage" : "text-sand hover:text-ink"
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
