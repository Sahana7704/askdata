"use client";

import { useSearchParams } from "next/navigation";
import React, { Suspense } from "react";
import Answer from "@/components/ask/Answer";
import Composer from "@/components/ask/Composer";
import Pipeline, { LoadingPipeline } from "@/components/ask/Pipeline";
import ResultChart from "@/components/ask/ResultChart";
import ResultTable from "@/components/ask/ResultTable";
import SqlPanel from "@/components/ask/SqlPanel";
import { Banner, Card, Empty } from "@/components/ui";
import { useApp } from "@/lib/AppContext";

function AskPage() {
  const { result, loading, error, ask, health, healthError } = useApp();
  const prefill = useSearchParams().get("q") ?? undefined;

  return (
    <>
      <Composer onSubmit={ask} loading={loading} initial={prefill} />
      {healthError && <Banner tone="error">{healthError}</Banner>}
      {health && !health.llm.configured && (
        <Banner tone="warn">
          No model API key is set, so questions can’t be answered yet. Set <code className="font-mono">ASKDATA_GEMINI_API_KEY</code> (free) or <code className="font-mono">ASKDATA_ANTHROPIC_API_KEY</code> on the backend and restart it. The Schema page works without it.
        </Banner>
      )}
      {error && <Banner tone="error">{error}</Banner>}
      {loading && <LoadingPipeline />}
      {!loading && result && (
        <>
          <Pipeline result={result} />
          {result.status === "ok" && (
            <>
              <Answer result={result} />
              {result.chart && <ResultChart key={result.id ?? result.question} chart={result.chart} title={result.question} />}
              <ResultTable key={`t-${result.id ?? result.question}`} result={result} />
            </>
          )}
          {result.status === "unanswerable" && (
            <Card><Empty icon="help_outline" title="This database doesn’t have that information">{result.error}</Empty></Card>
          )}
          {result.status === "failed" && (
            <Banner tone="error">
              <div className="font-medium">Couldn’t write a working query for this question.</div>
              <div className="mt-1 font-mono text-label-code-sm">{result.error}</div>
              <div className="mt-1 text-on-surface-variant">Try rewording it, or name the table or column you mean.</div>
            </Banner>
          )}
          <SqlPanel result={result} />
        </>
      )}
      {!loading && !result && !error && (
        <Card><Empty icon="table_view" title="No question yet">
          Results show up here: a short answer, a chart when the data suits one, the rows, and the SQL that produced them.
        </Empty></Card>
      )}
    </>
  );
}

export default function Page() {
  return <Suspense fallback={null}><AskPage /></Suspense>;
}
