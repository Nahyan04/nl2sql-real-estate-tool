import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { SchemaTable } from "@/lib/types";

const SUBJECTS = [
  { table: "transactions", en: "Sales transactions", ar: "معاملات البيع" },
  { table: "rental_observations", en: "Residential leasing", ar: "الإيجارات السكنية" },
  { table: "price_indices", en: "Price and rent trends", ar: "اتجاهات الأسعار والإيجارات" },
] as const;

export function DataSurface({ tables, arabic }: { tables: SchemaTable[]; arabic: boolean }) {
  const names = new Set(tables.map((table) => table.name));
  const subjects = SUBJECTS.filter((subject) => names.has(subject.table));
  return (
    <aside>
      <div className="border-s-2 border-sage/35 ps-5">
        <p className="text-sm font-semibold text-sage">{arabic ? "البيانات وراء الإجابة" : "The data behind the answer"}</p>
        <p className="mt-2 text-base leading-relaxed text-sand">
          {(subjects.length ? subjects : SUBJECTS).map((subject) => arabic ? subject.ar : subject.en).join(" · ")}
        </p>
      </div>
      <Link href={`/data${arabic ? "?lang=ar" : ""}`} className="mt-2 ms-5 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-sage hover:underline underline-offset-4">
        {arabic ? "استكشف البيانات" : "Explore the data"}<ArrowUpRight className="size-4 rtl:-scale-x-100" aria-hidden />
      </Link>
    </aside>
  );
}
