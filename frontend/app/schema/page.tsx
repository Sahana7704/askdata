"use client";

import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import SchemaGraph from "@/components/SchemaGraph";
import { Banner, Button, Card, Empty, Icon, Pill } from "@/components/ui";
import { api, SchemaInfo, SchemaTable } from "@/lib/api";
import { useApp } from "@/lib/AppContext";
import { formatNumber, timeAgo } from "@/lib/format";

function Stat({ label, value, sub, icon }: { label: string; value: React.ReactNode; sub?: string; icon: string }) {
  return (
    <div className="flex items-start justify-between rounded-lg border border-outline-variant bg-surface-container-low p-space-md">
      <div>
        <div className="text-label-code-sm font-medium text-on-surface-variant">{label}</div>
        <div className="mt-1 font-mono text-data-metric text-on-surface">{value}</div>
        {sub && <div className="mt-0.5 text-label-code-sm text-on-surface-variant">{sub}</div>}
      </div>
      <Icon name={icon} className="text-xl text-on-surface-variant/60" />
    </div>
  );
}

function TableCard({ t, active, open, onToggle }: { t: SchemaTable; active: boolean; open: boolean; onToggle: () => void }) {
  const router = useRouter();
  return (
    <Card className="gap-space-md">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full flex-wrap items-center gap-space-sm text-left">
        <Icon name="table_chart" className="text-xl text-on-surface-variant" />
        <span className="font-mono text-headline-sm font-semibold">{t.name}</span>
        {active && <Pill tone="teal">Used by last question</Pill>}
        <span className="text-label-code-sm text-on-surface-variant">{formatNumber(t.row_count, { compact: true })} rows, {t.columns.length} columns</span>
        <Icon name="expand_more" className={`ml-auto text-on-surface-variant transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <>
          {t.comment && <p className="text-body-sm text-on-surface-variant">{t.comment}</p>}
          <div className="overflow-x-auto rounded border border-outline-variant">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-lowest text-label-code-sm font-medium text-on-surface-variant">
                  {["Column", "Type", "Constraints", "Description"].map((h) => <th key={h} className="border-b border-outline-variant/30 px-4 py-2.5 font-normal">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {t.columns.map((c) => (
                  <tr key={c.name} className="align-top hover:bg-surface-container-high">
                    <td className="border-b border-outline-variant/10 px-4 py-2.5 font-mono text-body-sm">
                      {c.primary_key && <Icon name="key" className="mr-1 align-middle text-sm text-tertiary" />}{c.name}
                    </td>
                    <td className="border-b border-outline-variant/10 px-4 py-2.5 font-mono text-label-code-sm text-secondary">{c.type}</td>
                    <td className="border-b border-outline-variant/10 px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {c.primary_key && <Pill>PK</Pill>}
                        {c.fk && <Pill tone="violet">FK to {c.fk}</Pill>}
                        {!c.nullable && !c.primary_key && <Pill>NOT NULL</Pill>}
                      </div>
                    </td>
                    <td className="border-b border-outline-variant/10 px-4 py-2.5 text-body-sm text-on-surface-variant">
                      {c.comment}
                      {c.sample_values.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{c.sample_values.map((v) => <span key={v} className="rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-code-sm">{v}</span>)}</div>}
                      {c.value_range && <div className="mt-1 font-mono text-label-code-sm">{c.value_range[0]} to {c.value_range[1]}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end">
            <Button onClick={() => router.push(`/?q=${encodeURIComponent(`Give me an overview of the ${t.name} table`)}`)}>
              Ask about this table
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

export default function SchemaPage() {
  const { result } = useApp();
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [query, setQuery] = useState("");
  const [onlyActive, setOnlyActive] = useState(false);
  const [openSet, setOpenSet] = useState<Set<string>>(new Set());

  const load = useCallback(() => api.schema().then((s) => { setSchema(s); setError(null); }).catch((e: Error) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const active = useMemo(() => result?.tables_used?.length ? result.tables_used : result?.retrieved_tables ?? [], [result]);
  const sync = async () => { setSyncing(true); try { await api.refreshSchema(); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Sync failed"); } finally { setSyncing(false); } };

  const shown = useMemo(() => {
    if (!schema) return [];
    const q = query.trim().toLowerCase();
    return schema.tables.filter((t) => {
      if (onlyActive && !active.includes(t.name)) return false;
      if (!q) return true;
      return t.name.toLowerCase().includes(q) || (t.comment ?? "").toLowerCase().includes(q) ||
        t.columns.some((c) => c.name.toLowerCase().includes(q) || (c.comment ?? "").toLowerCase().includes(q));
    });
  }, [schema, query, onlyActive, active]);

  const toggle = (n: string) => setOpenSet((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x; });
  const cols = schema?.tables.reduce((a, t) => a + t.columns.length, 0) ?? 0;

  return (
    <>
      <div className="flex flex-col justify-between gap-space-md md:flex-row md:items-end">
        <div>
          <h1 className="text-headline-lg font-semibold">Schema</h1>
          <p className="max-w-xl text-body-sm text-on-surface-variant">The tables, columns and links between tables that the model sees when it writes SQL. Descriptions come from the comments stored in the database.</p>
        </div>
        <Button onClick={sync} disabled={syncing}><Icon name="sync" className={`text-lg ${syncing ? "animate-spin" : ""}`} />{syncing ? "Reloading" : "Reload schema"}</Button>
      </div>

      {error && <Banner tone="error">{error}</Banner>}

      {schema && (
        <>
          <div className="grid grid-cols-1 gap-space-md sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Database" value={<span className="text-headline-md">{schema.database}</span>} sub="PostgreSQL" icon="database" />
            <Stat label="Tables" value={schema.tables.length} icon="table" />
            <Stat label="Columns" value={cols} icon="view_column" />
            <Stat label="Last loaded" value={<span className="text-headline-md">{timeAgo(schema.built_at)}</span>} sub={`${schema.relationships.length} foreign keys`} icon="schedule" />
          </div>

          <Card>
            <div className="flex items-center gap-3 rounded border border-outline-variant px-3 py-2">
              <Icon name="search" className="text-on-surface-variant" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search schema" placeholder="Search tables, columns or descriptions"
                className="w-full bg-transparent text-body-md text-on-surface placeholder-on-surface-variant/60 focus:outline-none" />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setOnlyActive(false)} className={`rounded border px-3 py-1 text-label-code-sm ${!onlyActive ? "border-outline bg-surface-container-high text-on-surface" : "border-outline-variant text-on-surface-variant hover:text-on-surface"}`}>All tables ({schema.tables.length})</button>
              <button disabled={!active.length} onClick={() => setOnlyActive(true)} className={`rounded border px-3 py-1 text-label-code-sm disabled:opacity-40 ${onlyActive ? "border-outline bg-surface-container-high text-on-surface" : "border-outline-variant text-on-surface-variant hover:text-on-surface"}`}>Used by last question ({active.length})</button>
              
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-space-lg xl:grid-cols-[1fr_380px]">
            <div className="flex flex-col gap-space-md">
              {shown.length ? shown.map((t) => <TableCard key={t.name} t={t} active={active.includes(t.name)} open={openSet.has(t.name) || (!!query.trim() && shown.length <= 3)} onToggle={() => toggle(t.name)} />)
                : <Card><Empty icon="search_off" title="No tables match">Try a different search term.</Empty></Card>}
            </div>
            <div className="flex flex-col gap-space-md xl:sticky xl:top-20 xl:self-start">
              <Card>
                <span className="text-headline-sm font-semibold">How tables connect</span>
                <p className="text-body-sm text-on-surface-variant">Arrows are foreign keys. Tables used by your last question are highlighted.</p>
                <SchemaGraph tables={schema.tables} relationships={schema.relationships} active={active} />
              </Card>
            </div>
          </div>
        </>
      )}
      {!schema && !error && <Card><Empty icon="hourglass_top" title="Loading schema" /></Card>}
    </>
  );
}
