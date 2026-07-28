import { formatCell, humanizeColumn, looksNumericColumn } from "@/lib/format";
import type { Cell } from "@/lib/types";

interface ResultsTableProps {
  columns: string[];
  rows: Cell[][];
  rowCount: number;
  truncated: boolean;
}

function firstValue(rows: Cell[][], index: number): Cell {
  return rows.find((row) => row[index] !== null)?.[index] ?? null;
}

export function ResultsTable({ columns, rows, rowCount, truncated }: ResultsTableProps) {
  if (columns.length === 0) return null;

  const numeric = columns.map((column, index) => looksNumericColumn(column, firstValue(rows, index)));

  return (
    <section className="mt-12">
      <div className="flex items-baseline justify-between gap-6">
        <h2 className="label-mono">Result</h2>
        <p className="label-mono text-sand">
          {rowCount} {rowCount === 1 ? "row" : "rows"} · {columns.length}{" "}
          {columns.length === 1 ? "column" : "columns"}
        </p>
      </div>

      <div className="mt-4 max-h-[26rem] overflow-auto rounded-lg border border-rule bg-paper">
        <table className="w-full border-collapse text-[1rem] font-medium">
          <thead className="sticky top-0 z-10 bg-paper">
            <tr>
              {columns.map((column, index) => (
                <th
                  key={column}
                  scope="col"
                  className={`label-mono border-b border-rule px-4 py-3 whitespace-nowrap ${
                    numeric[index] ? "text-end" : "text-start"
                  }`}
                >
                  {humanizeColumn(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-rule/60 last:border-b-0">
                {row.map((cell, cellIndex) => (
                  <td
                    key={cellIndex}
                    dir="auto"
                    className={`px-4 py-2.5 whitespace-nowrap ${
                      numeric[cellIndex]
                        ? "text-end font-mono tabular-nums text-ink"
                        : "text-start text-sand"
                    }`}
                  >
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {truncated ? (
        <p className="mt-3 text-[0.9375rem] text-sand">
          Capped at {rowCount} rows. Add a filter or a time range to see a complete set.
        </p>
      ) : null}
    </section>
  );
}
