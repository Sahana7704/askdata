"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React from "react";
import { useApp } from "@/lib/AppContext";
import { Icon, Pill } from "./ui";

const NAV = [
  { href: "/", label: "Ask", icon: "chat" },
  { href: "/schema", label: "Schema", icon: "table_chart" },
  { href: "/evaluation", label: "Evaluation", icon: "fact_check" },
];

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 px-space-sm pb-space-lg">
      <img src="/icon.svg" alt="" width={28} height={28} className="rounded" />
      <span className="text-headline-sm font-semibold text-on-surface">AskData</span>
    </Link>
  );
}

function SourceCard() {
  const { health, healthError } = useApp();
  const db = health?.database && "name" in health.database ? health.database : null;
  const down = !!healthError || (health?.database && "error" in health.database);
  return (
    <div className="mx-space-md mb-space-md rounded-lg border border-outline-variant p-space-md">
      <div className="flex items-center justify-between text-label-code-sm">
        <span className="text-on-surface-variant">Database</span>
        <span className={`flex items-center gap-1.5 ${down ? "text-error" : db ? "text-secondary" : "text-on-surface-variant"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${down ? "bg-error" : db ? "bg-secondary" : "bg-on-surface-variant/50"}`} />
          {down ? "Offline" : db ? "Connected" : "Connecting"}
        </span>
      </div>
      <div className="mt-1.5 text-body-sm font-medium text-on-surface truncate">{db ? `PostgreSQL, ${db.name}` : down ? "Unavailable" : "Connecting..."}</div>
      {db && <div className="mt-0.5 text-label-code-sm text-on-surface-variant">{db.tables} tables</div>}
    </div>
  );
}

function Recent() {
  const { history, openHistory } = useApp();
  const router = useRouter();
  if (!history.length) return null;
  return (
    <div className="px-space-md">
      <div className="mb-1 px-space-sm text-label-code-sm font-medium text-on-surface-variant">Recent questions</div>
      <ul className="flex flex-col">
        {history.map((h) => (
          <li key={h.id}>
            <button
              onClick={() => { openHistory(h.id); router.push("/"); }}
              className="w-full truncate rounded px-space-sm py-1.5 text-left text-body-sm text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
              title={h.question}>
              {h.status !== "ok" && <Icon name="error_outline" className="mr-1 align-middle text-sm text-tertiary" />}
              {h.question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Footer({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap gap-x-4 gap-y-1 text-label-code-sm text-on-surface-variant ${className}`}>
      <Link href="/privacy" className="hover:text-on-surface hover:underline">Privacy</Link>
      <Link href="/terms" className="hover:text-on-surface hover:underline">Terms</Link>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { health, healthError } = useApp();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <div className="min-h-screen">
      <aside className="fixed left-0 top-0 z-40 hidden h-full w-64 flex-col border-r border-outline-variant bg-surface-container-low lg:flex">
        <div className="flex-1 overflow-y-auto pt-space-lg">
          <div className="px-space-md"><Logo /></div>
          <nav className="mb-space-lg flex flex-col gap-0.5 px-space-md">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href}
                className={`flex items-center gap-space-sm rounded px-space-sm py-2 text-body-sm ${isActive(n.href) ? "bg-surface-container-high text-on-surface font-medium" : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"}`}>
                <Icon name={n.icon} className="text-xl" />
                {n.label}
              </Link>
            ))}
          </nav>
          <SourceCard />
          <Recent />
        </div>
        <div className="flex flex-col gap-2 border-t border-outline-variant px-space-lg py-space-md">
          <div className="text-label-code-sm text-on-surface-variant">Model: {health?.llm.model ?? "not set"}</div>
          <Footer />
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant bg-surface px-4 py-3 lg:px-margin">
          <div className="flex items-center gap-1 lg:hidden">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={`rounded px-3 py-1.5 text-body-sm ${isActive(n.href) ? "bg-surface-container-high text-on-surface" : "text-on-surface-variant"}`}>{n.label}</Link>
            ))}
          </div>
          <div className="hidden lg:block" />
          <div className="flex flex-wrap items-center gap-2">
            <Pill>Read-only</Pill>
            {health && (health.llm.configured
              ? <Pill tone="teal">Model connected</Pill>
              : <Pill tone="amber">No API key</Pill>)}
            {healthError && <Pill tone="red">API offline</Pill>}
          </div>
        </header>
        <main className="mx-auto flex max-w-[1200px] flex-col gap-space-lg px-4 py-space-lg lg:px-margin">{children}</main>
        <Footer className="mx-auto max-w-[1200px] px-4 pb-space-lg lg:hidden" />
      </div>
    </div>
  );
}
