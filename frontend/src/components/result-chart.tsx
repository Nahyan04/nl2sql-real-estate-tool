"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCell, formatCompact, humanizeColumn, sentenceCase } from "@/lib/format";
import type { Cell, ChartSpec } from "@/lib/types";

/** Fixed order, never cycled. One series wears the brand gold; more than one
 *  needs the validated categorical set. */
const SOLO = "var(--sage)";
const SERIES = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

const AXIS = { fill: "var(--sand)", fontSize: 12, fontFamily: "var(--font-mono)" };
const GRID = "var(--rule)";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}/;
const MONTH_LABEL = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });

function formatAxisLabel(value: unknown): string {
  if (typeof value === "string" && ISO_DATE.test(value)) {
    return MONTH_LABEL.format(new Date(value));
  }
  return String(value ?? "");
}

/** A price index runs 100–160; anchoring it to zero flattens the whole story.
 *  Lines encode value by position, so they fit the data — bars, which encode it
 *  by length, keep their zero baseline. */
function fittedDomain([min, max]: readonly [number, number]): [number, number] {
  const pad = max > min ? (max - min) * 0.12 : Math.abs(max) * 0.1 || 1;
  const low = min >= 0 ? Math.max(0, min - pad) : min - pad;
  const high = max + pad;
  const step = niceStep((high - low) / 4);
  return [Math.floor(low / step) * step, Math.ceil(high / step) * step];
}

/** Snap to a round interval so the ticks read 130 / 140 / 150, not 128.38. */
function niceStep(raw: number): number {
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const normalized = raw / magnitude;
  const multiple = [1, 2, 2.5, 5, 10].find((candidate) => normalized <= candidate) ?? 10;
  return multiple * magnitude;
}

type Row = Record<string, Cell>;

function toRows(columns: string[], rows: Cell[][]): Row[] {
  return rows.map((row) => Object.fromEntries(columns.map((column, index) => [column, row[index]])));
}

/** A transaction count and an AED total cannot share an axis — the count
 *  collapses to nothing against a billions scale. A second axis would invent a
 *  correlation, so measures an order of magnitude apart get their own chart. */
function needsSmallMultiples(data: Row[], keys: string[]): boolean {
  if (keys.length < 2) return false;
  const peaks = keys.map((key) =>
    Math.max(...data.map((row) => Math.abs(Number(row[key]) || 0))),
  );
  const low = Math.min(...peaks);
  return low <= 0 || Math.max(...peaks) / low >= 10;
}

interface ResultChartProps {
  chart: ChartSpec;
  columns: string[];
  rows: Cell[][];
}

export function ResultChart({ chart, columns, rows }: ResultChartProps) {
  if (chart.type === "stat") {
    return <StatFigure chart={chart} columns={columns} rows={rows} />;
  }

  const data = toRows(columns, rows);
  const keys = chart.y_keys.filter((key) => columns.includes(key));
  const shown = keys.slice(0, SERIES.length);
  const xKey = chart.x_key;

  if (!xKey || shown.length === 0 || data.length === 0) return null;

  const faceted = needsSmallMultiples(data, shown);
  const colorFor = (index: number) => (shown.length === 1 ? SOLO : SERIES[index]);
  const Figure = chart.type === "line" ? LineFigure : BarFigure;

  return (
    <section className="mt-12">
      <div className="flex items-baseline justify-between gap-6">
        <h2 className="label-mono">Chart</h2>
        {shown.length > 1 && !faceted ? <Legend keys={shown} colorFor={colorFor} /> : null}
      </div>

      {faceted ? (
        <div className="mt-4 space-y-4">
          {shown.map((key, index) => (
            <figure key={key}>
              <figcaption className="text-[1.0625rem] text-ink">
                {sentenceCase(`${humanizeColumn(key)} by ${humanizeColumn(xKey)}`)}
              </figcaption>
              <div className="mt-3 rounded-lg border border-rule bg-paper p-5 pe-7">
                <Figure data={data} xKey={xKey} keys={[key]} colorFor={() => SERIES[index]} />
              </div>
            </figure>
          ))}
        </div>
      ) : (
        <>
          <p className="mt-3 text-[1.0625rem] text-ink">{chart.title}</p>
          <div className="mt-5 rounded-lg border border-rule bg-paper p-5 pe-7">
            <Figure data={data} xKey={xKey} keys={shown} colorFor={colorFor} />
          </div>
        </>
      )}

      {keys.length > shown.length ? (
        <p className="mt-3 text-[0.9375rem] text-sand">
          Charting the first {shown.length} measures. The rest are in the result table.
        </p>
      ) : null}
    </section>
  );
}

function StatFigure({ chart, columns, rows }: ResultChartProps) {
  const key = chart.y_keys[0] ?? columns[0];
  const index = columns.indexOf(key);
  const value = index >= 0 ? rows[0]?.[index] : null;
  if (value === undefined || value === null) return null;

  return (
    <section className="mt-12">
      <h2 className="label-mono">Result</h2>
      <p className="mt-4 text-[3.25rem] leading-none font-semibold text-ink">
        {formatCell(value)}
      </p>
      <p className="mt-3 text-[1.0625rem] text-sand">{chart.title}</p>
    </section>
  );
}

interface FigureProps {
  data: Row[];
  xKey: string;
  keys: string[];
  colorFor: (index: number) => string;
}

function LineFigure({ data, xKey, keys, colorFor }: FigureProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 24, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={AXIS}
          tickFormatter={formatAxisLabel}
          tickLine={false}
          axisLine={{ stroke: GRID }}
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          tickFormatter={(value) => formatCompact(Number(value))}
          tickLine={false}
          axisLine={false}
          width={64}
          domain={fittedDomain}
        />
        <Tooltip content={<ChartTooltip colorFor={colorFor} keys={keys} />} cursor={{ stroke: GRID }} />
        {keys.map((key, index) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={colorFor(index)}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--paper)" }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Rankings carry text categories, which collide as vertical tick labels;
 *  horizontal bars give every label a full line. */
function BarFigure({ data, xKey, keys, colorFor }: FigureProps) {
  const height = Math.max(200, data.length * (keys.length > 1 ? 30 * keys.length : 44) + 40);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barGap={2}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          tick={AXIS}
          tickFormatter={(value) => formatCompact(Number(value))}
          tickLine={false}
          axisLine={{ stroke: GRID }}
        />
        <YAxis
          type="category"
          dataKey={xKey}
          tick={AXIS}
          tickFormatter={formatAxisLabel}
          tickLine={false}
          tickMargin={10}
          axisLine={{ stroke: GRID }}
          width={158}
        />
        <Tooltip
          content={<ChartTooltip colorFor={colorFor} keys={keys} />}
          cursor={{ fill: "var(--secondary)" }}
        />
        {keys.map((key, index) => (
          <Bar key={key} dataKey={key} fill={colorFor(index)} radius={[0, 4, 4, 0]} maxBarSize={22} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function Legend({ keys, colorFor }: { keys: string[]; colorFor: (index: number) => string }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
      {keys.map((key, index) => (
        <li key={key} className="label-mono flex items-center gap-2 text-sand">
          <span
            aria-hidden
            className="size-2 shrink-0 rounded-full"
            style={{ background: colorFor(index) }}
          />
          {humanizeColumn(key)}
        </li>
      ))}
    </ul>
  );
}

interface TooltipProps {
  active?: boolean;
  label?: unknown;
  payload?: { dataKey?: string | number; value?: number }[];
  keys: string[];
  colorFor: (index: number) => string;
}

function ChartTooltip({ active, label, payload, keys, colorFor }: TooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-md border border-rule bg-paper px-3.5 py-2.5 shadow-[0_8px_24px_rgba(26,24,22,0.12)]">
      <p className="label-mono text-sand">{formatAxisLabel(label)}</p>
      <ul className="mt-2 space-y-1">
        {payload.map((entry) => {
          const key = String(entry.dataKey ?? "");
          return (
            <li key={key} className="flex items-center gap-2.5 text-[0.9375rem]">
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full"
                style={{ background: colorFor(keys.indexOf(key)) }}
              />
              <span className="text-sand">{humanizeColumn(key)}</span>
              <span className="ms-auto font-mono text-ink">{formatCell(entry.value ?? null)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
