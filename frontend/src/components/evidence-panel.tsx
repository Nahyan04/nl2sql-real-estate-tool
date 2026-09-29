import type { QueryResponse, SourceCoverage } from "@/lib/types";

function belongsToTable(source: SourceCoverage, table: string): boolean {
  const file = source.source_file;
  if (table === "transactions") return file === "Transactions/recent_sales_2019-2026.csv";
  if (table === "price_indices") return file.startsWith("Price Indices/") && file.endsWith("price_index.xlsx");
  if (table === "rental_observations") {
    return file.startsWith("Residential Leases/") || file === "Price Indices/average_sale_rent_prices_by_product_area.xlsx";
  }
  return table === "dataset_coverage";
}

function usedSourceFiles(sql: string): Set<string> {
  const files = new Set<string>();
  for (const match of sql.matchAll(/\bsource_file\s*=\s*'((?:[^']|'')+)'/gi)) {
    files.add(match[1].replaceAll("''", "'"));
  }
  return files;
}

function unitsFor(columns: string[], arabic: boolean): string[] {
  const units = new Set<string>();
  for (const column of columns) {
    const name = column.toLowerCase();
    if (name.endsWith("_aed_sqm")) {
      units.add(arabic ? "درهم/م²" : "AED/sqm");
      continue;
    }
    if (name.endsWith("_aed") || name.includes("price_aed") || name.includes("rent_aed")) units.add(arabic ? "درهم" : "AED");
    if (name.endsWith("_sqm")) units.add(arabic ? "م²" : "sqm");
    if (name.endsWith("_pct") || name.endsWith("_percent")) units.add("%");
    if (/(?:^|_)count(?:_|$)/.test(name) || name.includes("units")) units.add(arabic ? "عدد" : "count");
    if (name.endsWith("_index") || name.includes("index_value")) units.add(arabic ? "مستوى المؤشر" : "index level");
    if (name.includes("share")) units.add(arabic ? "حصة الملكية" : "ownership fraction");
  }
  return [...units];
}

interface EvidencePanelProps {
  result: QueryResponse;
  coverage: SourceCoverage[];
  schemaSnapshotId: string | null;
  arabic: boolean;
}

export function EvidencePanel({ result, coverage, schemaSnapshotId, arabic }: EvidencePanelProps) {
  const snapshotMatches = result.snapshot_id !== null && result.snapshot_id === schemaSnapshotId;
  const namedFiles = usedSourceFiles(result.sql);
  const sources = snapshotMatches
    ? coverage.filter((source) =>
        namedFiles.has(source.source_file) ||
        (result.tables_used.includes("transactions") && belongsToTable(source, "transactions")),
      )
    : [];
  const units = unitsFor(result.columns, arabic);
  const saleTypeScope = result.tables_used.includes("transactions") && result.columns.some((column) =>
    column.toLowerCase().includes("sale_type"),
  );
  const leaseScope = result.tables_used.includes("rental_observations") && result.columns.some((column) =>
    column.toLowerCase().includes("leased_units") || column.toLowerCase().includes("active_value"),
  );
  const labels = arabic ? {
    heading: "الدليل والنطاق",
    snapshot: "نسخة البيانات",
    tables: "الجداول المستخدمة",
    method: "طريقة إعداد الاستعلام",
    sourcePlan: "خطة استعلام موثقة",
    modelQuery: "استعلام أنشأه النموذج",
    units: "وحدات النتائج",
    dates: "شروط التاريخ في SQL المنفذ",
    noDates: "لم يُحدد شرط تاريخ في الاستعلام.",
    sourceCoverage: "تغطية المصادر",
    limitedResult: "نتيجة الاستعلام محدودة؛ قد لا تشمل كل السجلات المطابقة.",
    limitedAnswer: "استخدم الشرح أول 50 صفًا فقط؛ يعرض الجدول كل الصفوف المُعادة.",
    saleTypeScope: "نوع البيع هو تصنيف المصدر؛ القيم بالدرهم والأعداد تمثل سجلات البيع المصدّرة.",
    leaseScope: "قيمة الإيجار تخص الفترة المحددة؛ الوحدات المؤجرة رصيد في نهاية الربع.",
  } : {
    heading: "Evidence & scope",
    snapshot: "Source snapshot",
    tables: "Query tables",
    method: "Query preparation",
    sourcePlan: "Verified query plan",
    modelQuery: "Model-generated SQL",
    units: "Units in result",
    dates: "Date conditions in executed SQL",
    noDates: "No date filter in the query.",
    sourceCoverage: "Source coverage",
    limitedResult: "The query result was capped. The answer may cover only part of the matching data.",
    limitedAnswer: "The explanation used only the first 50 returned rows; the result table contains the full returned set.",
    saleTypeScope: "Sale type is the source category; values are AED and counts are exported sales observations.",
    leaseScope: "Lease value covers the stated period; leased units are a quarter-end count.",
  };

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="min-w-0 rounded-xl border border-rule bg-paper-flat px-5 py-5 sm:px-6" aria-label={labels.heading}>
      <h2 className="section-heading">{labels.heading}</h2>
      <dl className="mt-5 grid gap-x-7 gap-y-5 border-t border-rule pt-5 sm:grid-cols-2 md:grid-cols-1 xl:grid-cols-2">
        <div>
          <dt className="label-mono text-sand">{labels.method}</dt>
          <dd className="evidence-copy mt-1 text-sm text-ink">
            {result.query_method?.startsWith("source_plan:") ? labels.sourcePlan : labels.modelQuery}
          </dd>
        </div>
        <div>
          <dt className="label-mono text-sand">{labels.snapshot}</dt>
          <dd className="evidence-copy mt-1 break-words font-mono text-sm text-ink">{result.snapshot_id ?? (arabic ? "غير متاحة" : "Unavailable")}</dd>
        </div>
        <div>
          <dt className="label-mono text-sand">{labels.tables}</dt>
          <dd dir="ltr" className="evidence-copy mt-1 break-words font-mono text-sm text-ink">{result.tables_used.join(" · ") || (arabic ? "لا توجد" : "None")}</dd>
        </div>
        {units.length > 0 ? (
          <div>
            <dt className="label-mono text-sand">{labels.units}</dt>
            <dd className="evidence-copy mt-1 text-sm text-ink">{units.join(" · ")}</dd>
          </div>
        ) : null}
        <div>
          <dt className="label-mono text-sand">{labels.dates}</dt>
          <dd className="evidence-copy mt-1 text-sm text-ink">
            {result.date_conditions.length > 0 ? (
              <ul className="space-y-1">
                {result.date_conditions.map((condition) => (
                  <li key={condition} dir="ltr" className="break-words font-mono text-xs leading-relaxed">{condition}</li>
                ))}
              </ul>
            ) : labels.noDates}
          </dd>
        </div>
      </dl>
      {saleTypeScope || leaseScope ? (
        <p className="mt-5 border-s-2 border-rule ps-3 text-sm leading-relaxed text-sand">
          {[saleTypeScope ? labels.saleTypeScope : null, leaseScope ? labels.leaseScope : null].filter(Boolean).join(" ")}
        </p>
      ) : null}
      {result.answer_limited ? (
        <p className="mt-5 border-s-2 border-sage ps-3 text-sm leading-relaxed text-sand">
          {result.truncated ? labels.limitedResult : labels.limitedAnswer}
        </p>
      ) : null}
      {sources.length > 0 ? (
        <details className="mt-5 border-t border-rule pt-4">
          <summary className="cursor-pointer text-sm font-medium text-sage">{labels.sourceCoverage} · {sources.length}</summary>
          <ul className="mt-3 space-y-3 text-sm text-sand">
            {sources.map((source) => (
              <li key={source.source_file} className="border-s-2 border-rule ps-3">
                <span dir="ltr" className="block break-all font-mono text-xs text-ink">{source.source_file}</span>
                <span className="mt-1 block">
                  {arabic ? "ملاحظات من" : "Observed"} {source.observed_from ?? (arabic ? "غير معروف" : "unknown")}
                  {arabic ? "إلى" : "to"} {source.observed_through ?? (arabic ? "غير معروف" : "unknown")}
                  {source.complete_through
                    ? ` · ${arabic ? "فترة مكتملة حتى" : "Complete through"} ${source.complete_through}`
                    : arabic ? " · اكتمال الفترة غير مؤكد" : " · Complete period unconfirmed"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
