"use client";

import React, { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Chart, ChartType } from "@/lib/api";
import { COLORS, formatNumber } from "@/lib/format";
import { Card, Icon } from "../ui";

const LABELS: Record<string, { label: string; icon: string }> = {
  bar: { label: "Bar", icon: "bar_chart" }, line: { label: "Line", icon: "show_chart" },
  donut: { label: "Donut", icon: "donut_large" }, grid: { label: "Grid", icon: "table" },
};
const XKEY = "__x";
const axis = { stroke: "#8b8e95", fontSize: 11, fontFamily: "JetBrains Mono, monospace" };

function Tip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color?: string; payload?: Record<string, unknown> }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded border border-outline-variant bg-surface-container-high px-3 py-2">
      <div className="mb-1 font-mono text-label-code-sm text-on-surface-variant">{label ?? payload[0].name}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 font-mono text-label-code-sm text-on-surface">
          <span className="h-2 w-2 rounded-sm" style={{ background: p.color ?? (p.payload?.fill as string) }} />{p.name}: {formatNumber(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function ResultChart({ chart, title }: { chart: Chart; title: string }) {
  const [type, setType] = useState<ChartType>(chart.type);
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const on = () => setNarrow(window.innerWidth < 640);
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  if (chart.type === "stat" || chart.type === "grid" || !chart.data.length) return null;
  const common = { data: chart.data, margin: { top: 8, right: 8, left: 0, bottom: 0 } };
  const tilt = chart.data.length > (narrow ? 3 : 8);
  const show = type === "grid" ? "bar" : type;

  return (
    <Card>
      <div className="flex flex-col justify-between gap-space-sm sm:flex-row sm:items-center">
        <div>
          <div className="text-headline-sm font-semibold">{title}</div>
          <div className="text-label-code-sm text-on-surface-variant">{chart.data.length} points</div>
        </div>
        <div className="flex gap-0.5 rounded border border-outline-variant p-0.5">
          {chart.available.filter((a) => a !== "grid").map((a) => (
            <button key={a} onClick={() => setType(a)} aria-pressed={type === a}
              className={`flex items-center gap-1 rounded px-2.5 py-1 text-body-sm ${type === a ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant hover:text-on-surface"}`}>
              <Icon name={LABELS[a].icon} className="text-base" />{LABELS[a].label}
            </button>
          ))}
        </div>
      </div>
      <div className="h-80 p-space-xs">
        <ResponsiveContainer width="100%" height="100%">
          {show === "donut" ? (
            <PieChart>
              <Pie data={chart.data} dataKey={chart.series[0]} nameKey={XKEY} innerRadius="55%" outerRadius="85%" paddingAngle={2} stroke="none">
                {chart.data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip content={<Tip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          ) : show === "line" ? (
            <LineChart {...common}>
              <CartesianGrid stroke="#2a2c31" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={XKEY} {...axis} tickLine={false} axisLine={{ stroke: "#34363c" }} />
              <YAxis {...axis} tickLine={false} axisLine={false} tickFormatter={(v) => formatNumber(v, { compact: true })} width={56} />
              <Tooltip content={<Tip />} />
              {chart.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {chart.series.map((s, i) => <Line key={s} type="monotone" dataKey={s} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={chart.data.length < 25} connectNulls />)}
            </LineChart>
          ) : (
            <BarChart {...common}>
              <CartesianGrid stroke="#2a2c31" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={XKEY} {...axis} tickLine={false} axisLine={{ stroke: "#34363c" }} interval={0} angle={tilt ? -35 : 0} textAnchor={tilt ? "end" : "middle"} height={tilt ? 70 : 30} />
              <YAxis {...axis} tickLine={false} axisLine={false} tickFormatter={(v) => formatNumber(v, { compact: true })} width={56} />
              <Tooltip content={<Tip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              {chart.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {chart.series.map((s, i) => <Bar key={s} dataKey={s} stackId={chart.stacked ? "a" : undefined} fill={COLORS[i % COLORS.length]} radius={chart.stacked ? 0 : [2, 2, 0, 0]} />)}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
