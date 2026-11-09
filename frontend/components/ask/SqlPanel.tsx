"use client";

import React, { useState } from "react";
import type { AskResult } from "@/lib/api";
import { highlightSql } from "@/lib/sqlHighlight";
import { Button, Card, Icon, Pill } from "../ui";

export default function SqlPanel({ result }: { result: AskResult }) {
  const [open, setOpen] = useState(true);
  const [copied, setCopied] = useState(false);
  if (!result.sql) return null;
  const verified = result.trace.some((t) => t.step === "validate" && t.status === "ok") && result.status === "ok";
  const copy = async () => {
    try { await navigator.clipboard.writeText(result.sql); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* blocked */ }
  };
  return (
    <Card className="gap-space-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button onClick={() => setOpen((o) => !o)} className="flex flex-wrap items-center gap-space-sm text-left" aria-expanded={open}>
                    <span className="text-headline-sm font-semibold">{result.status === "ok" ? "SQL" : "Last SQL tried"}</span>
          {verified && <Pill>Read-only, checked before running</Pill>}
          <Icon name="expand_more" className={`text-on-surface-variant transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        <Button onClick={copy}><Icon name={copied ? "check" : "content_copy"} className="text-base" />{copied ? "Copied" : "Copy SQL"}</Button>
      </div>
      {open && (
        <>
          {result.repairs > 0 && result.first_error && (
            <div className="rounded border border-outline-variant px-3 py-2 text-label-code-sm text-on-surface-variant">
              <span>The first query failed (“{result.first_error.replace(/\.$/, "")}”), so the error was sent back to the model and it wrote this one instead.</span>
            </div>
          )}
          <pre className="overflow-x-auto rounded border border-outline-variant bg-surface-container-lowest p-space-md font-mono text-label-code-md leading-relaxed text-on-surface"><code>{highlightSql(result.sql)}</code></pre>
        </>
      )}
    </Card>
  );
}
