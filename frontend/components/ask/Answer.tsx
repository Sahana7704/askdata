import React from "react";
import type { AskResult } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { Banner } from "../ui";

export default function Answer({ result }: { result: AskResult }) {
  return (
    <section className="flex flex-col gap-space-md rounded-lg border border-outline-variant bg-surface-container-low p-space-lg">
      <div className="flex flex-col gap-space-xs">
        <span className="text-label-code-sm font-medium text-on-surface-variant">Answer</span>
        <p className="max-w-4xl text-body-lg leading-relaxed text-on-surface">{result.summary}</p>
      </div>
      {result.tiles.length > 0 && (
        <div className="grid grid-cols-1 gap-space-md sm:grid-cols-2 lg:grid-cols-4">
          {result.tiles.map((t) => (
            <div key={t.label} className="rounded border border-outline-variant p-space-md">
              <div className="truncate text-label-code-sm font-medium text-on-surface-variant" title={t.label}>{t.label.replace(/_/g, " ")}</div>
              <div className={`mt-1 truncate font-mono ${t.kind === "number" ? "text-data-metric" : "text-headline-md"} text-on-surface`} title={String(t.value)}>
                {t.kind === "number" ? formatNumber(t.value, { compact: true }) : t.value}
              </div>
              {t.sub && <div className="mt-0.5 font-mono text-label-code-sm text-on-surface-variant">{t.sub}</div>}
            </div>
          ))}
        </div>
      )}
      {result.truncated && <Banner tone="warn">Result truncated to {formatNumber(result.row_count)} rows. Tiles and charts reflect only the rows shown.</Banner>}
    </section>
  );
}
