const KEY = "bayan.history";
const LIMIT = 8;
const EMPTY: string[] = [];

/** Session history lives in localStorage and never leaves the browser. It is
 *  exposed as an external store so components read it with
 *  `useSyncExternalStore` — the server snapshot is empty, which is what the
 *  server render has to produce. */
let cache: string[] | null = null;
const listeners = new Set<() => void>();

function read(): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string").slice(0, LIMIT)
      : EMPTY;
  } catch {
    return EMPTY;
  }
}

function write(next: string[]) {
  cache = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // private browsing or a full quota — history is a convenience, not the record
  }
  listeners.forEach((listener) => listener());
}

export function subscribeHistory(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getHistory(): string[] {
  if (cache === null) cache = read();
  return cache;
}

export function getServerHistory(): string[] {
  return EMPTY;
}

export function pushHistory(question: string): void {
  write([question, ...getHistory().filter((item) => item !== question)].slice(0, LIMIT));
}

export function clearHistory(): void {
  write(EMPTY);
}
