import type { Metadata } from "next";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/material-symbols-outlined/fill.css";
import "./globals.css";
import { AppProvider } from "@/lib/AppContext";
import { SITE_URL } from "@/lib/site";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "AskData", template: "%s | AskData" },
  description: "Ask questions about a PostgreSQL database in plain English and get read-only SQL, a short answer and the rows behind it.",
  alternates: { canonical: "/" },
  icons: { icon: "/icon.svg" },
  openGraph: { type: "website", url: SITE_URL, siteName: "AskData", title: "AskData" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface text-on-surface antialiased">
        <AppProvider>
          <Shell>{children}</Shell>
        </AppProvider>
      </body>
    </html>
  );
}
