// Site-wide settings. Set these in frontend/.env.local (or your host's environment) before deploying.

/** Public address of the site, e.g. https://askdata.example.com. Used for canonical URLs and link previews. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

/** Who runs this deployment. Shown on the Privacy and Terms pages. */
export const OPERATOR = process.env.NEXT_PUBLIC_OPERATOR_NAME ?? "the operator of this site";

/** Where people can send privacy or legal questions. Leave empty to hide the contact line. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "";

/** Date the Privacy and Terms pages were last changed. Update it whenever you edit them. */
export const LEGAL_UPDATED = "9 November 2026";
