import type { Cell } from "./types";

const GROUPED = new Intl.NumberFormat("en-AE", { maximumFractionDigits: 2 });
const WHOLE = new Intl.NumberFormat("en-AE", { maximumFractionDigits: 0 });

/** Fils on a nine-figure AED total are noise; keep decimals for small numbers
 *  where they carry the precision (indices, rates, averages). */
function grouped(value: number): string {
  return Math.abs(value) >= 1000 ? WHOLE.format(value) : GROUPED.format(value);
}

/** Column names the seeded schema uses for money and for measured quantities. */
const NUMERIC_NAME = /(aed|price|value|rent|rate|count|total|avg|sum|index|area|sqm)/i;

export function isNumeric(value: Cell): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatCell(value: Cell): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (isNumeric(value)) return grouped(value);
  return String(value);
}

/** Axis and tick labels: AED 203bn reads where 203,000,000,000 does not. */
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${trim(value / 1e9)}bn`;
  if (abs >= 1e6) return `${trim(value / 1e6)}m`;
  if (abs >= 1e4) return `${trim(value / 1e3)}k`;
  return grouped(value);
}

function trim(value: number): string {
  return value.toFixed(Math.abs(value) < 10 ? 1 : 0).replace(/\.0$/, "");
}

/** Column labels come straight from the SQL; make them readable without
 *  losing the acronyms an analyst is looking for. */
const ACRONYMS = new Set(["aed", "sqm", "yoy", "ytd", "fdi", "gcc", "uae", "id", "avg"]);

export function humanizeColumn(column: string): string {
  return column
    .split("_")
    .filter(Boolean)
    .map((word) => (ACRONYMS.has(word.toLowerCase()) ? word.toUpperCase() : word))
    .join(" ");
}

/** Capitalize the sentence, never the acronyms inside it. */
export function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function looksNumericColumn(column: string, sample: Cell): boolean {
  return isNumeric(sample) || (sample === null && NUMERIC_NAME.test(column));
}
