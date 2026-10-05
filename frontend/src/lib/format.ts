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

export function formatMetricCell(value: Cell, column: string, arabic = false): string {
  if (!isNumeric(value)) return formatCell(value);
  const name = column.toLowerCase();
  if (name.endsWith("_aed_sqm")) return arabic ? `${GROUPED.format(value)} درهم/م²` : `AED ${GROUPED.format(value)}/sqm`;
  if (name.endsWith("_aed") && /(weighted|average|avg|per_unit)/.test(name)) {
    return arabic ? `${GROUPED.format(value)} درهم` : `AED ${GROUPED.format(value)}`;
  }
  if (name.endsWith("_aed")) return arabic ? `${GROUPED.format(value)} درهم` : `AED ${GROUPED.format(value)}`;
  if (/(?:^|_)(?:pct|percent|percentage)(?:_|$)/.test(name)) return `${GROUPED.format(value)}%`;
  if (name.endsWith("_sqm")) return arabic ? `${grouped(value)} م²` : `${grouped(value)} sqm`;
  if (/(?:^|_)count(?:_|$)/.test(name)) return WHOLE.format(value);
  return formatCell(value);
}

/** Axis and tick labels: AED 203bn reads where 203,000,000,000 does not. */
export function formatCompact(value: number, arabic = false): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${trim(value / 1e9)}${arabic ? " مليار" : "bn"}`;
  if (abs >= 1e6) return `${trim(value / 1e6)}${arabic ? " مليون" : "m"}`;
  if (abs >= 1e4) return `${trim(value / 1e3)}${arabic ? " ألف" : "k"}`;
  return grouped(value);
}

function trim(value: number): string {
  return value.toFixed(Math.abs(value) < 10 ? 1 : 0).replace(/\.0$/, "");
}

/** Column labels come straight from the SQL; make them readable without
 *  losing the acronyms an analyst is looking for. */
const ACRONYMS = new Set(["aed", "sqm", "yoy", "ytd", "fdi", "gcc", "uae", "id", "avg"]);

const ARABIC_COLUMNS: Record<string, string> = {
  district: "المنطقة", community: "المجتمع", municipality: "البلدية", project_name: "المشروع",
  transaction_date: "تاريخ البيع", period_end: "نهاية الفترة", source_file: "ملف المصدر",
  sales_value_aed: "قيمة المبيعات (درهم)", sales_observation_count: "عدد سجلات البيع",
  sale_type: "نوع البيع", leased_units_count: "عدد الوحدات المؤجرة",
  sales_count: "عدد سجلات المبيعات", sales_records_count: "عدد سجلات المبيعات",
  residential_lease_value_aed: "قيمة الإيجارات السكنية (درهم)",
  total_lease_value_aed: "قيمة الإيجارات (درهم)", rent_index_change_pct: "تغير مؤشر الإيجارات (%)",
  rent_index: "مستوى مؤشر الإيجارات", index_value: "مستوى المؤشر",
};

const ARABIC_WORDS: Record<string, string> = {
  sales: "المبيعات", sale: "البيع", value: "القيمة", price: "السعر", rent: "الإيجار",
  rental: "الإيجار", lease: "الإيجار", index: "المؤشر", change: "التغير",
  total: "الإجمالي", average: "المتوسط", avg: "المتوسط", annual: "السنوي",
  count: "العدد", observation: "السجلات", observations: "السجلات", units: "الوحدات",
  records: "السجلات", record: "السجل",
  district: "المنطقة", community: "المجتمع", property: "العقار", type: "النوع",
  area: "المساحة", sqm: "م²", aed: "درهم", pct: "%", percent: "%",
  year: "السنة", month: "الشهر", date: "التاريخ", source: "المصدر",
  weighted: "المرجح", gross: "الإجمالي", segment: "الشريحة", yield: "العائد",
  ratio: "النسبة", share: "الحصة", layout: "التصميم", active: "النشط",
};

export function humanizeColumn(column: string, arabic = false): string {
  if (arabic) {
    const salesCount = column.match(/^sales_(?:records_|observations_)?count_(\d{4})$/i);
    if (salesCount) return `عدد سجلات المبيعات لعام ${salesCount[1]}`;
    return ARABIC_COLUMNS[column] ?? column.split("_").filter(Boolean).map((word) => ARABIC_WORDS[word.toLowerCase()] ?? word).join(" ");
  }
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
