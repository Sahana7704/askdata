import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { OPERATOR } from "@/lib/site";

export const metadata: Metadata = { title: "Terms of use", alternates: { canonical: "/terms" } };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of use">
      <p>By using AskData you agree to these terms. The site is run by {OPERATOR}.</p>

      <h2>What the service does</h2>
      <p>
        AskData turns questions written in plain English into read-only SQL queries, runs them against the connected
        database and shows the results. The SQL is written by an AI model, so answers can be wrong.
      </p>

      <h2>Check the answers</h2>
      <ul>
        <li>Every answer shows the SQL that produced it. Check it before relying on a result.</li>
        <li>Do not use results as the only basis for financial, legal, medical or other important decisions.</li>
        <li>The demo database contains made-up data. It does not describe any real business or person.</li>
      </ul>

      <h2>Acceptable use</h2>
      <ul>
        <li>Do not try to change, delete or extract data you are not meant to see, or to get around the read-only and rate limits.</li>
        <li>Do not send automated traffic that overloads the service.</li>
        <li>Do not enter personal, confidential or sensitive information in questions. Other users can see recent questions.</li>
      </ul>

      <h2>Availability</h2>
      <p>The service is provided as is, without any guarantee that it will be available, accurate or error-free. It may be changed or switched off at any time.</p>

      <h2>Liability</h2>
      <p>To the extent the law allows, {OPERATOR} is not liable for any loss that comes from using the service or relying on its answers.</p>

      <h2>Changes</h2>
      <p>These terms may be updated. The date at the top of the page shows when they last changed. Continuing to use the site means you accept the current version.</p>
    </LegalPage>
  );
}
