"use client";

import type { Provider, ProvidersResponse } from "@/lib/types";

const OPTIONS: { value: Provider; label: string; hint: string }[] = [
  { value: "anthropic", label: "Cloud API", hint: "Questions and answer context are sent to the configured cloud model" },
  { value: "ollama", label: "Self-hosted", hint: "Uses the configured Ollama endpoint when it is available" },
];

interface ProviderToggleProps {
  value: Provider;
  onChange: (provider: Provider) => void;
  disabled: boolean;
  arabic?: boolean;
  availability: ProvidersResponse | null;
  failed?: boolean;
}

export function ProviderToggle({ value, onChange, disabled, arabic = false, availability, failed = false }: ProviderToggleProps) {
  if (availability === null) return <p className="text-sm text-sand" role="status">{failed ? (arabic ? "تعذر الاتصال بخدمة التحليل" : "Analysis service could not be reached") : (arabic ? "جارٍ التحقق من النموذج…" : "Checking model availability…")}</p>;
  const localAvailable = availability?.ollama.available === true;
  const cloudAvailable = availability?.anthropic.available === true;
  const localHint = localAvailable
    ? (arabic ? "نموذج Ollama المحلي متاح" : "Configured Ollama model is available")
    : (arabic ? "الاستضافة الذاتية غير متاحة حتى يتم التحقق من الخدمة والنموذج" : "Self-hosted is unavailable until its endpoint and model are verified");
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
              title={option.value === "ollama" ? localHint : (cloudAvailable ? (arabic ? "يرسل السؤال وسياق الإجابة إلى النموذج السحابي المهيأ" : option.hint) : (arabic ? "الخدمة السحابية غير مهيأة" : "Cloud API is not configured"))}
              disabled={disabled || !(availability?.[option.value].available ?? false)}
              aria-pressed={value === option.value}
              onClick={() => onChange(option.value)}
              className={`control-option min-h-10 cursor-pointer rounded-md px-2.5 py-1 transition-colors disabled:cursor-default disabled:opacity-50 ${
                value === option.value ? "bg-sage/10 text-sage" : "text-sand hover:text-ink"
              }`}
            >
              {arabic ? (option.value === "anthropic" ? "خدمة سحابية" : "استضافة ذاتية") : option.label}
              {option.value === "ollama" && !localAvailable ? <span className="ms-1 text-xs font-normal">{arabic ? " غير متاحة" : " unavailable"}</span> : null}
            </button>
          </span>
        ))}
      </div>
      {!cloudAvailable ? <span className="text-xs text-sand" role="status">{arabic ? "الخدمة السحابية غير متاحة" : "Cloud API unavailable"}</span> : null}
    </div>
  );
}
