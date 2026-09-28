import { ProviderToggle } from "@/components/provider-toggle";
import { Wordmark } from "@/components/wordmark";
import type { LanguageChoice, Provider } from "@/lib/types";

interface HeaderProps {
  provider: Provider;
  language: LanguageChoice;
  arabic: boolean;
  onProviderChange: (provider: Provider) => void;
  onLanguageChange: (language: LanguageChoice) => void;
  busy: boolean;
}

export function Header({ provider, language, arabic, onProviderChange, onLanguageChange, busy }: HeaderProps) {
  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex max-w-[68rem] flex-wrap items-center gap-x-8 gap-y-3 px-5 sm:px-8 py-5">
        <Wordmark />
        <p className="hidden text-[0.9375rem] text-sand lg:block">
          {arabic ? "تحليلات عقارية لأبوظبي باللغة الطبيعية" : <>Natural-language analytics for Abu Dhabi&rsquo;s real estate market</>}
        </p>
        <div className="ms-auto flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2" role="group" aria-label={arabic ? "لغة الإجابة" : "Answer language"}>
            <span className="label-mono text-sand">{arabic ? "اللغة" : "Language"}</span>
            {(["auto", "en", "ar"] as const).map((option) => (
              <button key={option} type="button" disabled={busy} aria-pressed={language === option}
                onClick={() => onLanguageChange(option)}
                className={`label-mono cursor-pointer disabled:cursor-default ${language === option ? "text-sage" : "text-sand hover:text-ink"}`}>
                {option === "auto" ? (arabic ? "تلقائي" : "Auto") : option === "en" ? "EN" : "عربي"}
              </button>
            ))}
          </div>
          <ProviderToggle value={provider} onChange={onProviderChange} disabled={busy} arabic={arabic} />
        </div>
      </div>
    </header>
  );
}
