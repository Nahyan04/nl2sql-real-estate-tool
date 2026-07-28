import { ProviderToggle } from "@/components/provider-toggle";
import { Wordmark } from "@/components/wordmark";
import type { Provider } from "@/lib/types";

interface HeaderProps {
  provider: Provider;
  onProviderChange: (provider: Provider) => void;
  busy: boolean;
}

export function Header({ provider, onProviderChange, busy }: HeaderProps) {
  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex max-w-[68rem] items-center gap-8 px-5 sm:px-8 py-5">
        <Wordmark />
        <p className="hidden text-[0.8125rem] text-sand lg:block">
          Natural-language analytics for Abu Dhabi&rsquo;s real estate market
        </p>
        <div className="ms-auto">
          <ProviderToggle value={provider} onChange={onProviderChange} disabled={busy} />
        </div>
      </div>
    </header>
  );
}
