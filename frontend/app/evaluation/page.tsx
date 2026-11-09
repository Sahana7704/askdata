"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Banner, Button, Card, Empty, Icon, Pill } from "@/components/ui";
import { api, ApiError, EvalRecord, EvalRun, EvalSummary } from "@/lib/api";
import { formatMs } from "@/lib/format";
import { highlightSql } from "@/lib/sqlHighlight";

const CONFIG_COLORS: Record<string, string> = { baseline: "#7d8590", schema: "#5b9cf0", repair: "#6cc28a" };
const FAILURE_LABEL: Record<string, { t: string; tone: "red" | "amber" }> = {
  wrong_result: { t: "Wrong result", tone: "amber" }, invalid_sql: { t: "Invalid SQL", tone: "red" }, refused: { t: "Refused", tone: "amber" },
};

function Metric({ label, value, unit, sub, bar, tone, badge }: { label: string; value: string; unit?: string; sub: React.ReactNode; bar?: number; tone: string; badge?: React.ReactNode }) {
  return (
    <Card>
      <div className="flex items-center justify-between"><span className="text-body-sm text-on-surface-variant">{label}</span>{badge}</div>
      <div className="flex items-baseline gap-2"><span className="font-mono text-display-lg text-on-surface">{value}</span>{unit && <span className="font-mono text-label-code-sm text-on-surface-variant">{unit}</span>}</div>
      {bar !== undefined && <div className="h-1.5 rounded-full bg-surface-container-high"><div className="h-full rounded-full" style={{ width: `${Math.min(100, bar)}%`, background: tone }} /></div>}
      <div className="text-body-sm text-on-surface-variant">{sub}</div>
    </Card>
  );
}

function Diagnostics({ records }: { records: EvalRecord[] }) {
  const failures = records.filter((r) => !r.correct);
  const healed = records.filter((r) => r.healed);
  const [tab, setTab] = useState<"fail" | "healed">("fail");
  const [page, setPage] = useState(0);
  const list = tab === "fail" ? failures : healed;
  const PER = 4;
  const pages = Math.max(1, Math.ceil(list.length / PER));
  const rows = list.slice(page * PER, page * PER + PER);
  return (
    <Card>
      <div className="flex flex-col justify-between gap-space-sm sm:flex-row sm:items-center">
        <div>
          <span className="text-headline-sm font-semibold">Misses and retries</span>
          <p className="text-body-sm text-on-surface-variant">For the full setup: expected and actual SQL for every wrong answer, and the questions that only passed after a retry.</p>
        </div>
        <div className="flex gap-0.5 rounded border border-outline-variant p-0.5 text-label-code-sm">
          {([["fail", `Wrong (${failures.length})`], ["healed", `Retried (${healed.length})`]] as const).map(([k, l]) => (
            <button key={k} onClick={() => { setTab(k); setPage(0); }} className={`rounded px-3 py-1 ${tab === k ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant hover:text-on-surface"}`}>{l}</button>
          ))}
        </div>
      </div>
      {!rows.length ? <Empty icon={tab === "fail" ? "check" : "replay"} title={tab === "fail" ? "No wrong answers in this run" : "Nothing needed a retry in this run"} /> : (
        <div className="flex flex-col gap-space-sm">
          {rows.map((r) => (
            <div key={r.case_id} className="grid gap-space-md rounded border border-outline-variant p-space-md md:grid-cols-[260px_1fr]">
              <div className="flex flex-col gap-2">
                <div className="text-body-sm font-medium text-on-surface">“{r.question}”</div>
                <div className="font-mono text-label-code-sm text-on-surface-variant">{r.case_id} · {r.category}</div>
                {r.healed ? <Pill tone="teal">Passed after {r.repairs} {r.repairs === 1 ? "retry" : "retries"}</Pill>
                  : r.failure && <Pill tone={FAILURE_LABEL[r.failure].tone}>{FAILURE_LABEL[r.failure].t}</Pill>}
              </div>
              <div className="flex min-w-0 flex-col gap-2">
                <div>
                  <div className="mb-1 font-mono text-label-code-sm uppercase text-on-surface-variant">Expected</div>
                  <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-container-lowest p-3 font-mono text-label-code-sm"><code>{highlightSql(r.expected_sql)}</code></pre>
                </div>
                {!r.healed && (
                  <div>
                    <div className="mb-1 font-mono text-label-code-sm uppercase text-on-surface-variant">Actual</div>
                    <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-container-lowest p-3 font-mono text-label-code-sm"><code>{r.actual_sql ? highlightSql(r.actual_sql) : <span className="text-on-surface-variant">(no SQL)</span>}</code></pre>
                  </div>
                )}
                {(r.error || r.first_error) && <div className="font-mono text-label-code-sm text-error/90">{r.healed ? `First error: ${r.first_error}` : r.error}</div>}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between font-mono text-label-code-sm text-on-surface-variant">
            <span>{page * PER + 1} to {Math.min(list.length, page * PER + PER)} of {list.length}</span>
            <div className="flex items-center gap-2">
              <Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
              <span>Page {page + 1} of {pages}</span>
              <Button variant="ghost" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function Results({ run }: { run: EvalRun }) {
  const res = run.result!;
  const s = res.summary;
  const full: EvalSummary = s.find((x) => x.key === "repair") ?? s[s.length - 1];
  const base = s[0];
  const delta = full.accuracy - base.accuracy;
  const cats = Object.keys(full.categories);
  const fullRecords = res.records.filter((r) => r.config === full.key);
  return (
    <>
      <div className="grid grid-cols-1 gap-space-md md:grid-cols-3">
        <Metric label="Accuracy" value={`${full.accuracy}`} unit="%" tone="#6cc28a" bar={full.accuracy}
          badge={s.length > 1 ? <Pill tone={delta >= 0 ? "teal" : "red"}>{delta >= 0 ? "+" : ""}{delta.toFixed(1)} points vs baseline</Pill> : undefined}
          sub={`${full.correct} of ${full.n} test questions returned the same rows as the reference query`} />
        <Metric label="Median time per question" value={formatMs(full.median_latency_ms)} tone="#7d8590" bar={Math.min(100, (full.median_latency_ms / 5000) * 100)}
          sub={`95% of questions finished within ${formatMs(full.p95_latency_ms)}. The summary step is skipped here.`} />
        <Metric label="Needed a retry" value={`${full.repair_rate}`} unit="%" tone="#e3a857" bar={full.repair_rate}
          sub={`${full.healed} questions were only right after the error was sent back to the model`} />
      </div>

      <div className="grid grid-cols-1 gap-space-lg xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <div className="flex items-center justify-between">
            <span className="text-headline-sm font-semibold">Each part switched on in turn</span>
            <span className="text-label-code-sm text-on-surface-variant">{res.n_cases} questions</span>
          </div>
          <div className="overflow-x-auto rounded border border-outline-variant">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-container-lowest text-label-code-sm font-medium text-on-surface-variant">
                  {["Setup", "Accuracy", "Median time", "Retried", "Invalid SQL", "Wrong rows"].map((h) => <th key={h} className="border-b border-outline-variant/30 px-3 py-2.5 font-normal">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {s.map((r) => (
                  <tr key={r.key} className={r.key === full.key ? "bg-surface-container" : ""}>
                    <td className="border-b border-outline-variant/10 px-3 py-3"><div className="text-body-sm font-medium">{r.label}</div><div className="text-label-code-sm text-on-surface-variant">{r.description}</div></td>
                    <td className={`border-b border-outline-variant/10 px-3 py-3 font-mono ${r.key === full.key ? "text-secondary font-semibold" : ""}`}>{r.accuracy}%</td>
                    <td className="border-b border-outline-variant/10 px-3 py-3 font-mono">{formatMs(r.median_latency_ms)}</td>
                    <td className="border-b border-outline-variant/10 px-3 py-3 font-mono">{r.key === "repair" ? `${r.repair_rate}%` : "n/a"}</td>
                    <td className="border-b border-outline-variant/10 px-3 py-3 font-mono text-tertiary">{r.invalid_sql}</td>
                    <td className="border-b border-outline-variant/10 px-3 py-3 font-mono text-error">{r.wrong_result}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <span className="text-headline-sm font-semibold">Accuracy by question type</span>
            <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-label-code-sm text-on-surface-variant">
              {s.map((r) => <span key={r.key} className="flex items-center gap-1 whitespace-nowrap"><span className="h-2 w-2 rounded-full" style={{ background: CONFIG_COLORS[r.key] }} />{r.label.replace("+ ", "+")}</span>)}
            </div>
          </div>
          <div className="flex flex-col gap-space-md">
            {cats.map((c) => (
              <div key={c}>
                <div className="mb-1 flex justify-between text-body-sm"><span className="capitalize">{c}</span><span className="font-mono text-label-code-sm text-on-surface-variant">{full.categories[c].n} cases</span></div>
                {s.map((r) => (
                  <div key={r.key} className="mb-1 flex items-center gap-2">
                    <div className="h-2 flex-1 rounded-full bg-surface-container-high"><div className="h-full rounded-full" style={{ width: `${r.categories[c]?.accuracy ?? 0}%`, background: CONFIG_COLORS[r.key] }} /></div>
                    <span className="w-12 text-right font-mono text-label-code-sm">{r.categories[c]?.accuracy ?? 0}%</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Diagnostics records={fullRecords} />

      <div className="rounded-lg border border-outline-variant p-space-md text-body-sm text-on-surface-variant">
        <div className="mb-1 font-medium text-on-surface">How this is scored</div>
        A generated query counts as correct if running it returns the same rows as the hand-written reference query (row order and column names ignored, numbers compared to 2 decimals).
        The {res.n_cases} questions were written by hand for the demo database, so use these numbers to catch regressions in this project. They are not a general measure of text-to-SQL quality.
      </div>
    </>
  );
}

export default function EvaluationPage() {
  const [run, setRun] = useState<EvalRun | null>(null);
  const [info, setInfo] = useState<{ cases: number; llm: { configured: boolean; model: string } } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => api.evalLatest().then(setRun).catch((e: Error) => setError(e.message)), []);
  useEffect(() => { refresh(); api.evalInfo().then(setInfo).catch(() => {}); }, [refresh]);
  useEffect(() => {
    if (run?.status === "running") { timer.current = setInterval(refresh, 2000); }
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [run?.status, refresh]);

  const start = async () => {
    setStarting(true); setError(null);
    try { await api.evalRun(); await refresh(); } catch (e) { setError(e instanceof ApiError ? e.message : "Could not start evaluation"); } finally { setStarting(false); }
  };

  const running = run?.status === "running";
  const pct = running && run.progress.total ? Math.round(((run.progress.done ?? 0) / run.progress.total) * 100) : 0;
  const noKey = info && !info.llm.configured;

  return (
    <>
      <div className="flex flex-col justify-between gap-space-md md:flex-row md:items-end">
        <div>
          <h1 className="text-headline-lg font-semibold">Evaluation</h1>
          <p className="mt-1 max-w-2xl text-body-sm text-on-surface-variant">Runs a fixed set of test questions{info ? ` (${info.cases})` : ""} three times: with the whole schema, with table selection, and with retries on errors. Each answer is compared with a hand-written reference query.</p>
          {run?.result && <p className="mt-1 text-label-code-sm text-on-surface-variant">Last run {new Date(run.result.finished_at * 1000).toLocaleString()}</p>}
        </div>
        <Button variant="primary" onClick={start} disabled={starting || running || !!noKey} className="px-4 py-2">
          {running ? "Running" : "Run evaluation"}
        </Button>
      </div>

      {noKey && <Banner tone="warn">Running an evaluation calls the LLM, so it needs <code className="font-mono">ASKDATA_GEMINI_API_KEY</code> (free) or <code className="font-mono">ASKDATA_ANTHROPIC_API_KEY</code> on the backend. A full run makes roughly {info ? info.cases * 3 : 96}+ model calls.</Banner>}
      {error && <Banner tone="error">{error}</Banner>}
      {(run?.status === "failed" || run?.status === "interrupted") && <Banner tone="error">The last evaluation {run.status === "failed" ? `failed: ${run.progress.error ?? "unknown error"}` : "was interrupted (the backend restarted). Run it again."}</Banner>}

      {running && (
        <Card>
          <div className="flex items-center justify-between"><span className="text-headline-sm font-semibold">Running</span><span className="font-mono text-label-code-sm text-on-surface-variant">{run.progress.done ?? 0} of {run.progress.total ?? "?"} ({run.progress.config}, {run.progress.case})</span></div>
          <div className="h-1.5 rounded-full bg-surface-container-high"><div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
        </Card>
      )}

      {run?.status === "complete" && run.result && <Results run={run} />}
      {(!run || run.status === "none") && !error && (
        <Card><Empty icon="fact_check" title="No evaluation yet">
          Run it to see how often the model gets the test questions right, and how much table selection and retries help. Results appear here once a run finishes.
        </Empty></Card>
      )}
    </>
  );
}
