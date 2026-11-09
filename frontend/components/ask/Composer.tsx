"use client";

import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "../ui";

export default function Composer({ onSubmit, loading, initial }: { onSubmit: (q: string) => void; loading: boolean; initial?: string }) {
  const [q, setQ] = useState(initial ?? "");
  const [examples, setExamples] = useState<string[]>([]);

  useEffect(() => { api.examples().then(setExamples).catch(() => {}); }, []);
  useEffect(() => { if (initial) setQ(initial); }, [initial]);

  const submit = (text = q) => {
    const t = text.trim();
    if (t.length >= 3 && !loading) onSubmit(t);
  };

  return (
    <section className="flex flex-col gap-space-md">
      <div>
        <h1 className="text-headline-lg font-semibold">Ask a question</h1>
        <p className="text-body-sm text-on-surface-variant">Questions are turned into a single read-only SQL query against the shop database. You can see the query below every answer.</p>
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        className="flex flex-col gap-2 rounded-lg border border-outline-variant bg-surface-container-low p-2 focus-within:border-outline sm:flex-row sm:items-center">
        <label htmlFor="nl-input" className="sr-only">Question</label>
        <input
          id="nl-input" value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} autoFocus
          placeholder="e.g. Which state had the most canceled orders in 2018?"
          className="w-full flex-1 bg-transparent px-2 py-1.5 text-body-md text-on-surface placeholder-on-surface-variant/60 focus:outline-none" />
        <button type="submit" disabled={loading || q.trim().length < 3}
          className="flex items-center justify-center gap-1.5 rounded bg-primary px-4 py-2 text-body-sm font-medium text-on-primary hover:bg-primary-fixed-dim disabled:cursor-not-allowed disabled:opacity-50">
          {loading && <Icon name="progress_activity" className="animate-spin text-lg" />}
          {loading ? "Running" : "Run query"}
        </button>
      </form>
      {examples.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-label-code-sm text-on-surface-variant">Examples:</span>
          {examples.map((ex) => (
            <button key={ex} type="button" disabled={loading} onClick={() => { setQ(ex); submit(ex); }}
              className="rounded border border-outline-variant px-2 py-1 text-label-code-sm text-on-surface-variant hover:border-outline hover:text-on-surface disabled:opacity-50">
              {ex}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
