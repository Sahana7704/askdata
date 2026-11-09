"use client";

import React, { useMemo, useState } from "react";
import type { AskResult, Cell } from "@/lib/api";
import { download, formatCell, toCsv } from "@/lib/format";
import { Button, Card, Icon } from "../ui";

const PAGE = 10;

export default function ResultTable({ result }: { result: AskResult }) {
  const { columns, rows } = result;
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);

  const view = useMemo(() => {
    let r = rows;
    const f = filter.trim().toLowerCase();
    if (f) r = r.filter((row) => row.some((c) => String(c ?? "").toLowerCase().includes(f)));
    if (sort) {
      const { col, dir } = sort;
      r = [...r].sort((a, b) => {
        const x = a[col], y = b[col];
        if (x === y) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
      });
    }
    return r;
  }, [rows, filter, sort]);

  const pages = Math.max(1, Math.ceil(view.length / PAGE));
  const cur = Math.min(page, pages - 1);
  const slice = view.slice(cur * PAGE, cur * PAGE + PAGE);
  const isNum = (c: Cell) => typeof c === "number";

  const copyJson = async () => {
    const objs = view.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));
    try { await navigator.clipboard.writeText(JSON.stringify(objs, null, 2)); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };

  return (
    <Card>
      <div className="flex flex-col justify-between gap-space-md sm:flex-row sm:items-center">
        <div className="flex items-center gap-space-sm">
          <span className="text-headline-sm font-semibold">Rows</span>
          <span className="text-label-code-sm text-on-surface-variant">{result.row_count} {result.row_count === 1 ? "row" : "rows"}</span>
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          <div className="flex items-center gap-2 rounded border border-outline-variant px-3 py-1.5 text-on-surface-variant">
            <Icon name="filter_list" className="text-sm" />
            <input value={filter} onChange={(e) => { setFilter(e.target.value); setPage(0); }} placeholder="Filter rows" aria-label="Filter rows"
              className="w-36 bg-transparent text-body-sm text-on-surface placeholder-on-surface-variant focus:outline-none sm:w-48" />
          </div>
          <Button onClick={() => download("askdata-result.csv", toCsv(columns, view))}><Icon name="file_download" className="text-base" />Export CSV</Button>
          <Button onClick={copyJson}><Icon name={copied ? "check" : "content_copy"} className="text-base" />{copied ? "Copied" : "Copy JSON"}</Button>
        </div>
      </div>
      <div className="overflow-x-auto rounded border border-outline-variant">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {columns.map((c, i) => (
                <th key={c} className={`border-b border-outline-variant/30 px-4 py-3 font-mono text-label-code-sm font-normal text-on-surface-variant ${rows.length && isNum(rows[0][i]) ? "text-right" : ""}`}>
                  <button onClick={() => setSort((s) => (s?.col === i ? (s.dir === 1 ? { col: i, dir: -1 } : null) : { col: i, dir: 1 }))} className="inline-flex items-center gap-1 hover:text-on-surface">
                    {c.replace(/_/g, " ")}
                    <Icon name={sort?.col === i ? (sort.dir === 1 ? "arrow_upward" : "arrow_downward") : "unfold_more"} className="text-sm" />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.map((row, ri) => (
              <tr key={ri} className="hover:bg-surface-container">
                {row.map((cell, ci) => (
                  <td key={ci} className={`border-b border-outline-variant/10 px-4 py-3 text-body-sm ${isNum(cell) ? "text-right font-mono" : ""} ${cell === null ? "text-on-surface-variant/50 italic" : "text-on-surface"}`}>{formatCell(cell)}</td>
                ))}
              </tr>
            ))}
            {!slice.length && <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-body-sm text-on-surface-variant">No rows match the filter.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-label-code-sm text-on-surface-variant">
        <span>{view.length ? cur * PAGE + 1 : 0} to {Math.min(view.length, cur * PAGE + PAGE)} of {view.length}</span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" disabled={cur === 0} onClick={() => setPage(cur - 1)}>Previous</Button>
          <span>Page {cur + 1} of {pages}</span>
          <Button variant="ghost" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>Next</Button>
        </div>
      </div>
    </Card>
  );
}
