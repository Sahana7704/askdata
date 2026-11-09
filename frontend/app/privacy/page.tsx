import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";
import { OPERATOR } from "@/lib/site";

export const metadata: Metadata = { title: "Privacy policy", alternates: { canonical: "/privacy" } };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy">
      <p>
        This page explains what happens to information when you use AskData. The site is run by {OPERATOR}. There are
        no user accounts, no advertising and no tracking.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Your questions.</strong> Each question you type is saved on the server with the SQL that was written for it, the result rows, a short summary and how long it took.</li>
        <li><strong>Your IP address, briefly.</strong> It is held in memory for up to a few minutes to limit how many questions one address can send. It is not written to disk.</li>
        <li><strong>Standard server logs.</strong> The web server may log requests (time, address, page) for troubleshooting.</li>
      </ul>
      <p>We do not ask for your name, email or any other personal details. Please do not type personal or sensitive information into questions.</p>

      <h2>Who can see your questions</h2>
      <p>
        The &quot;Recent questions&quot; list is shared. Anyone using this site can see recent questions and their results,
        because there are no separate accounts.
      </p>

      <h2>Third parties</h2>
      <p>
        To answer a question, the text of the question, a description of the database tables (including a few
        example values from some columns), and up to 20 result rows are sent to the AI model provider configured for this site (Google Gemini or Anthropic Claude). Their
        handling of that data is covered by their own terms and privacy policies. Nothing else is shared or sold.
      </p>

      <h2>Cookies and tracking</h2>
      <p>The site sets no cookies and uses no analytics or tracking scripts. Fonts and icons are served from this site, not from a third party.</p>

      <h2>How long data is kept</h2>
      <p>Saved questions and evaluation runs stay on the server until the operator deletes them. To ask for a question to be removed, use the contact below.</p>

      <h2>Changes</h2>
      <p>If this policy changes, the date at the top of the page will change too.</p>
    </LegalPage>
  );
}
