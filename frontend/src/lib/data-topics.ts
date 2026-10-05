import type { SourceCoverage } from "@/lib/types";

export const DATA_TOPICS = [
  {
    id: "sales", table: "transactions", files: ["Transactions/recent_sales_2019-2026.csv"],
    en: { title: "Sales transactions", description: "Compare sales value and activity across districts, communities, projects, property types, and sale types.", measures: "Sales value · Sales observations · Price per sqm", units: "AED · observations · AED/sqm", grain: "Individual exported sales observations", question: "Which five districts had the highest sales value in 2025?" },
    ar: { title: "معاملات البيع", description: "قارن قيمة المبيعات ونشاطها حسب المناطق والمجتمعات والمشاريع وأنواع العقارات والبيع.", measures: "قيمة المبيعات · عدد سجلات البيع · سعر المتر المربع", units: "درهم · سجل · درهم/م²", grain: "سجلات البيع الفردية المصدّرة", question: "ما المناطق الخمس الأعلى من حيث قيمة المبيعات في عام 2025؟" },
  },
  {
    id: "leasing", table: "rental_observations", files: ["Residential Leases/lease_residential.xlsx", "Residential Leases/lease_price_by_period.xlsx", "Residential Leases/average_annual_rents_over_time.xlsx", "Price Indices/average_sale_rent_prices_by_product_area.xlsx"],
    en: { title: "Residential leasing", description: "Understand residential lease value, quarter-end leased units, and annual rent estimates by area and apartment layout.", measures: "Residential lease value · Leased units · Annual rent estimates", units: "AED · units · AED/year", grain: "Monthly and quarterly observations by source", question: "What was the residential lease value for Q1 and Q2 2026, in AED?" },
    ar: { title: "الإيجارات السكنية", description: "استكشف قيمة الإيجارات السكنية والوحدات المؤجرة في نهاية الربع وتقديرات الإيجار السنوي حسب المنطقة والتخطيط.", measures: "قيمة الإيجارات السكنية · الوحدات المؤجرة · تقديرات الإيجار السنوي", units: "درهم · وحدة · درهم/سنة", grain: "بيانات شهرية وربع سنوية حسب المصدر", question: "ما مجموع قيمة الإيجارات السكنية الواردة في المصدر للربعين الأول والثاني من 2026 بالدرهم؟" },
  },
  {
    id: "trends", table: "price_indices", files: ["Price Indices/sale_price_index.xlsx", "Price Indices/rent_price_index.xlsx", "Price Indices/office_price_index.xlsx", "Price Indices/retail_price_index.xlsx", "Price Indices/industrial_price_index.xlsx"],
    en: { title: "Price and rent indices", description: "Track sale and rent index levels and percentage changes across the available municipalities, property groups, and rental series.", measures: "Sale price indices · Rent indices · Percentage changes", units: "Index level · %", grain: "Monthly observations within each index series", question: "What was the percentage change from June 2025 to June 2026 in the Abu Dhabi City all-rents index for all residential property types and all zones?" },
    ar: { title: "مؤشرات الأسعار والإيجارات", description: "تابع مستويات مؤشرات البيع والإيجارات ونسب تغيرها حسب البلديات والمجموعات العقارية والسلاسل المتاحة.", measures: "مؤشرات أسعار البيع · مؤشرات الإيجارات · نسب التغير", units: "مستوى المؤشر · %", grain: "بيانات شهرية ضمن كل سلسلة مؤشر", question: "ما نسبة التغير من يونيو 2025 إلى يونيو 2026 في مؤشر جميع الإيجارات لجميع أنواع العقارات السكنية وجميع المناطق في مدينة أبوظبي؟" },
  },
] as const;

export function topicCoverage(coverage: SourceCoverage[], files: readonly string[]) {
  const sources = coverage.filter((source) => files.includes(source.source_file));
  const from = sources.flatMap((source) => source.observed_from ? [source.observed_from] : []).sort()[0];
  const through = sources.flatMap((source) => source.observed_through ? [source.observed_through] : []).sort().at(-1);
  return { from, through, sources };
}

export function displayDate(date: string, arabic: boolean) {
  return new Intl.DateTimeFormat(arabic ? "ar-AE-u-nu-latn" : "en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${date.slice(0, 10)}T00:00:00Z`));
}
