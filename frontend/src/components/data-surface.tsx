import type { SchemaTable } from "@/lib/types";

const SUBJECTS = [
  { table: "transactions", en: "Sales transactions", ar: "معاملات البيع" },
  { table: "rental_observations", en: "Rental observations", ar: "بيانات الإيجارات" },
  { table: "price_indices", en: "Price and rent indices", ar: "مؤشرات الأسعار والإيجارات" },
] as const;

export function DataSurface({ tables, arabic }: { tables: SchemaTable[]; arabic: boolean }) {
  const names = new Set(tables.map((table) => table.name));
  const subjects = SUBJECTS.filter((subject) => names.has(subject.table));
  if (subjects.length === 0) return null;

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="rounded-xl border border-rule bg-paper-flat px-5 py-5 sm:px-6">
      <h2 className="section-heading">{arabic ? "المواضيع المتاحة" : "Available data"}</h2>
      <ul className="mt-5 space-y-3 border-t border-rule pt-5">
        {subjects.map((subject) => (
          <li key={subject.table} className="flex items-baseline gap-3 text-[1rem] font-medium text-ink">
            <span className="size-1.5 shrink-0 rounded-full bg-sage" aria-hidden />
            {arabic ? subject.ar : subject.en}
          </li>
        ))}
      </ul>
    </section>
  );
}
