import { ProviderToggle } from "@/components/provider-toggle";
import { Wordmark } from "@/components/wordmark";
import type { LanguageChoice, Provider, ProvidersResponse } from "@/lib/types";

interface HeaderProps {
  provider: Provider;
  language: LanguageChoice;
  arabic: boolean;
  onProviderChange: (provider: Provider) => void;
  onLanguageChange: (language: LanguageChoice) => void;
  busy: boolean;
  availability: ProvidersResponse | null;
}

export function Header({ provider, language, arabic, onProviderChange, onLanguageChange, busy, availability }: HeaderProps) {
  return (
    <header dir={arabic ? "rtl" : "ltr"} className="border-b border-rule bg-paper-flat/80">
      <div className="mx-auto grid max-w-[88rem] gap-5 px-5 py-5 sm:px-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:px-12">
        <div className="flex min-w-0 items-center gap-5 sm:gap-7">
          <Wordmark />
          <p className="header-subtitle max-w-[24rem] border-s border-rule ps-5 text-[0.9375rem] font-medium leading-snug text-ink sm:ps-7">
            {arabic ? "تحليلات عقارية لأبوظبي باللغة الطبيعية" : <>Natural-language analytics for Abu Dhabi&rsquo;s real estate market</>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-x-7 gap-y-3 border-t border-rule pt-4 lg:justify-end lg:border-0 lg:pt-0">
          <div className="flex flex-wrap items-center gap-2.5" role="group" aria-label={arabic ? "لغة الإجابة" : "Answer language"}>
            <span className="control-label me-1">{arabic ? "اللغة" : "Language"}</span>
            {(["auto", "en", "ar"] as const).map((option) => (
              <button key={option} type="button" disabled={busy} aria-pressed={language === option}
                onClick={() => onLanguageChange(option)}
                className={`control-option cursor-pointer rounded-sm px-1.5 py-1 transition-colors disabled:cursor-default ${language === option ? "bg-sage/10 text-sage" : "text-sand hover:text-ink"}`}>
                {option === "auto" ? (arabic ? "تلقائي" : "Auto") : option === "en" ? "EN" : "عربي"}
              </button>
            ))}
          </div>
          <ProviderToggle value={provider} onChange={onProviderChange} disabled={busy} arabic={arabic} availability={availability} />
        </div>
      </div>
    </header>
  );
}
