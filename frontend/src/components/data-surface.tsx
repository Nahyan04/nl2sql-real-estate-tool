import type { SchemaTable } from "@/lib/types";

const DATE_TYPE = /^(date|timestamp)/i;

/** A table carrying a date column is a fact table; the rest describe it. */
function isFact(table: SchemaTable) {
  return table.columns.some((column) => DATE_TYPE.test(column.type));
}

export function DataSurface({ tables }: { tables: SchemaTable[] }) {
  if (tables.length === 0) return null;

  const groups = [
    { label: "Facts", names: tables.filter(isFact).map((table) => table.name) },
    { label: "Reference", names: tables.filter((table) => !isFact(table)).map((table) => table.name) },
  ].filter((group) => group.names.length > 0);

  return (
    <section className="mt-16 border-t border-rule pt-5">
      <h2 className="label-mono">What you can ask about</h2>
      <dl className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-[auto_1fr]">
        {groups.map((group) => (
          <div key={group.label} className="contents">
            <dt className="label-mono pt-px text-sand">{group.label}</dt>
            <dd className="font-mono text-[0.9375rem] leading-relaxed text-sand">
              {group.names.join("  ·  ")}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
