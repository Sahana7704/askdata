"use client";

import React, { useState } from "react";
import type { AskResult, TraceStep } from "@/lib/api";
import { formatMs } from "@/lib/format";
import { Icon, Pill } from "../ui";

const STEPS: { key: TraceStep["step"]; n: string; label: string }[] = [
  { key: "schema", n: "01", label: "Pick tables" },
  { key: "generate", n: "02", label: "Write SQL" },
  { key: "validate", n: "03", label: "Check SQL" },
  { key: "execute", n: "04", label: "Run" },
  { key: "summarize", n: "05", label: "Summary" },
];

const TONE = {
  ok: { text: "text-secondary", border: "border-outline-variant", icon: "check_circle", bg: "" },
  warn: { text: "text-tertiary", border: "border-tertiary/40", icon: "warning", bg: "" },
  error: { text: "text-error", border: "border-error/40", icon: "cancel", bg: "" },
  none: { text: "text-on-surface-variant/60", border: "border-outline-variant border-dashed", icon: "radio_button_unchecked", bg: "" },
} as const;

type Card = { key: string; n: string; label: string; tone: keyof typeof TONE; ms?: number; detail: string };

function buildCards(r: AskResult): Card[] {
  const cards: Card[] = [];
  for (const s of STEPS) {
    const entries = r.trace.filter((t) => t.step === s.key);
    if (!entries.length) { cards.push({ key: s.key, n: s.n, label: s.label, tone: "none", detail: "Not reached" }); continue; }
    const last = entries[entries.length - 1];
    cards.push({ key: s.key, n: s.n, label: s.label, tone: last.status, ms: entries.reduce((a, e) => a + e.ms, 0), detail: last.detail });
    if (s.key === "validate" && r.repairs > 0) {
      const reps = r.trace.filter((t) => t.step === "repair");
      cards.push({ key: "repair", n: "03b", label: "Retried", tone: "warn", ms: reps.reduce((a, e) => a + e.ms, 0),
        detail: `${r.repairs} ${r.repairs === 1 ? "retry" : "retries"}. ${r.first_error ?? ""}` });
    }
  }
  return cards;
}

export function LoadingPipeline() {
  return (
    <section className="flex flex-col gap-space-md rounded-lg border border-outline-variant bg-surface-container-low p-space-md">
      <div className="flex items-center gap-space-sm">
        <span className="text-headline-sm font-semibold">Working on it</span>
        <span className="text-label-code-sm text-on-surface-variant">This usually takes a few seconds.</span>
      </div>
      <div className="grid grid-cols-2 gap-space-sm md:grid-cols-5">
        {STEPS.map((s) => <div key={s.key} className="rounded border border-dashed border-outline-variant p-space-sm text-body-sm text-on-surface-variant">{s.label}</div>)}
      </div>
    </section>
  );
}

export default function Pipeline({ result }: { result: AskResult }) {
  const [logs, setLogs] = useState(false);
  const cards = buildCards(result);
  const badge =
    result.status === "ok"
      ? result.repairs > 0 ? { t: "Answered after a retry", tone: "teal" as const, i: "check" } : { t: "Answered", tone: "teal" as const, i: "check" }
      : result.status === "unanswerable" ? { t: "Not in this database", tone: "amber" as const, i: "help" } : { t: "Failed", tone: "red" as const, i: "error" };
  return (
    <section className="flex flex-col gap-space-md rounded-lg border border-outline-variant bg-surface-container-low p-space-md">
      <div className="flex flex-col justify-between gap-space-sm sm:flex-row sm:items-center">
        <div className="flex flex-wrap items-center gap-space-sm">
          <div className={`h-2.5 w-2.5 rounded-full ${result.status === "ok" ? "bg-secondary" : result.status === "failed" ? "bg-error" : "bg-tertiary"}`} />
          <span className="text-headline-sm font-semibold">Steps</span>
          <span className="font-mono text-label-code-sm text-on-surface-variant">{formatMs(result.latency_ms)} total</span>
          <Pill tone={badge.tone}><Icon name={badge.i} className="text-xs" />{badge.t}</Pill>
        </div>
        <button onClick={() => setLogs((v) => !v)}
          className="flex items-center gap-1 self-start rounded border border-outline-variant px-2.5 py-1 text-label-code-sm text-on-surface-variant hover:text-on-surface">
          {logs ? "Hide" : "Show"} log
          <Icon name="expand_more" className={`text-sm transition-transform ${logs ? "rotate-180" : ""}`} />
        </button>
      </div>
      <div className={`grid grid-cols-2 gap-space-sm ${cards.length > 5 ? "md:grid-cols-6" : "md:grid-cols-5"}`}>
        {cards.map((c) => {
          const t = TONE[c.tone];
          return (
            <div key={c.key} className={`flex flex-col rounded border p-space-sm ${t.bg} ${t.border}`}>
              <div className="mb-1.5 flex items-center justify-between">
                <span className={`flex items-center gap-1 font-mono text-label-code-sm ${t.text}`}><Icon name={t.icon} fill className="text-sm" />{c.n}</span>
                {c.ms !== undefined && <span className="font-mono text-label-code-sm text-on-surface-variant">{formatMs(c.ms)}</span>}
              </div>
              <div className="text-body-sm font-semibold text-on-surface">{c.label}</div>
              <div className="mt-0.5 line-clamp-3 font-mono text-label-code-sm text-on-surface-variant" title={c.detail}>{c.detail}</div>
            </div>
          );
        })}
      </div>
      {logs && (
        <div className="overflow-x-auto rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-md font-mono text-label-code-sm">
          {result.trace.map((t, i) => (
            <div key={i} className="whitespace-pre-wrap">
              <span className="text-on-surface-variant">[{String(i + 1).padStart(2, "0")}]</span>{" "}
              <span className={t.status === "ok" ? "text-secondary" : t.status === "warn" ? "text-tertiary" : "text-error"}>{t.step.padEnd(9)}</span>{" "}
              <span className="text-on-surface-variant">{formatMs(t.ms).padStart(7)}</span>{" "}
              <span className="text-on-surface">{t.detail}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
