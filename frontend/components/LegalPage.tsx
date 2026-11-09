import React from "react";
import { CONTACT_EMAIL, LEGAL_UPDATED } from "@/lib/site";

export function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <article className="max-w-3xl text-body-md leading-relaxed text-on-surface [&_h2]:mt-space-lg [&_h2]:mb-space-sm [&_h2]:text-headline-sm [&_h2]:font-semibold [&_p]:mb-space-md [&_p]:text-on-surface-variant [&_ul]:mb-space-md [&_ul]:list-disc [&_ul]:pl-6 [&_li]:mb-1 [&_li]:text-on-surface-variant [&_a]:underline [&_strong]:text-on-surface">
      <h1 className="text-headline-lg font-semibold">{title}</h1>
      <p className="mt-1 text-body-sm">Last updated {LEGAL_UPDATED}</p>
      {children}
      <h2>Contact</h2>
      {CONTACT_EMAIL
        ? <p>Questions about this page: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>
        : <p>Contact the person or organisation that gave you access to this site.</p>}
    </article>
  );
}
