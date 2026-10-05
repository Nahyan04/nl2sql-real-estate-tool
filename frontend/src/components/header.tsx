import Link from "next/link";
import { ProviderToggle } from "@/components/provider-toggle";
import { Wordmark } from "@/components/wordmark";
import type { LanguageChoice, Provider, ProvidersResponse } from "@/lib/types";

interface HeaderProps {
  provider?: Provider;
  language: LanguageChoice;
  arabic: boolean;
  onProviderChange?: (provider: Provider) => void;
  onLanguageChange: (language: LanguageChoice) => void;
  busy: boolean;
  availability?: ProvidersResponse | null;
  availabilityFailed?: boolean;
  page?: "ask" | "data";
}

export function Header({ provider, language, arabic, onProviderChange, onLanguageChange, busy, availability, availabilityFailed = false, page = "ask" }: HeaderProps) {
  const languages: LanguageChoice[] = page === "data" ? ["en", "ar"] : ["auto", "en", "ar"];
  return (
    <header dir={arabic ? "rtl" : "ltr"} className="border-b border-rule bg-paper-flat/80">
      <a href="#main-content" className="skip-link">{arabic ? "انتقل إلى المحتوى" : "Skip to content"}</a>
      <div className="mx-auto grid max-w-[88rem] gap-4 px-5 py-4 sm:px-8 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center lg:px-12">
        <div className="flex min-w-0 items-center gap-4 sm:gap-6">
          <Wordmark />
          <nav aria-label={arabic ? "التنقل الرئيسي" : "Main navigation"} className="flex flex-wrap gap-x-6 gap-y-1 border-s border-rule ps-4 sm:ps-6">
            {(["ask", "data"] as const).map((item) => <Link key={item} href={`${item === "ask" ? "/" : "/data"}${arabic ? "?lang=ar" : ""}`} aria-current={page === item ? "page" : undefined} className={`nav-link ${page === item ? "text-ink after:bg-sage" : "text-sand"}`}>
              {item === "ask" ? (arabic ? "اسأل بيان" : "Ask Bayan") : (arabic ? "استكشف البيانات" : "Explore the data")}
            </Link>)}
          </nav>
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-rule pt-3 xl:justify-end xl:border-0 xl:pt-0">
          <div className="flex items-center gap-1" role="group" aria-label={arabic ? "لغة الإجابة" : "Answer language"}>
            <span className="control-label me-2">{arabic ? "اللغة" : "Language"}</span>
            {languages.map((option) => <button key={option} type="button" disabled={busy} aria-pressed={language === option} onClick={() => onLanguageChange(option)} className={`control-option min-h-10 cursor-pointer rounded-md px-2.5 py-1 transition-colors disabled:cursor-default ${language === option ? "bg-sage/10 text-sage" : "text-sand hover:bg-sage/5 hover:text-ink"}`}>
              {option === "auto" ? (arabic ? "تلقائي" : "Auto") : option === "en" ? "EN" : "عربي"}
            </button>)}
          </div>
          {provider && onProviderChange ? <ProviderToggle value={provider} onChange={onProviderChange} disabled={busy} arabic={arabic} availability={availability ?? null} failed={availabilityFailed} /> : null}
        </div>
      </div>
    </header>
  );
}
