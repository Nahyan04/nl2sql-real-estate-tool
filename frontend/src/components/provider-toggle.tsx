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
  arabic?: boolean;
}

export function ProviderToggle({ value, onChange, disabled, arabic = false }: ProviderToggleProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="control-label">{arabic ? "النموذج" : "Model"}</span>
      <div className="flex items-center gap-2">
        {OPTIONS.map((option, index) => (
          <span key={option.value} className="flex items-center gap-2">
            {index > 0 ? (
              <span aria-hidden className="text-sand/30">
                ·
              </span>
            ) : null}
            <button
              type="button"
              title={arabic ? (option.value === "anthropic" ? "يرسل السؤال وسياق الإجابة إلى النموذج السحابي المهيأ" : "يستخدم خدمة Ollama المهيأة عند توفرها") : option.hint}
              disabled={disabled}
              aria-pressed={value === option.value}
              onClick={() => onChange(option.value)}
              className={`control-option cursor-pointer rounded-sm px-1.5 py-1 transition-colors disabled:cursor-default ${
                value === option.value ? "bg-sage/10 text-sage" : "text-sand hover:text-ink"
              }`}
            >
              {arabic ? (option.value === "anthropic" ? "خدمة سحابية" : "استضافة ذاتية") : option.label}
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
