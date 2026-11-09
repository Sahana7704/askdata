import type { Cell } from "./api";

export const COLORS = ["#5b9cf0", "#e3a857", "#6cc28a", "#ef6f6c", "#4fb3bf", "#c98b5b", "#9aa0a6", "#7d8590"];

export function formatNumber(v: unknown, opts: { compact?: boolean } = {}): string {
  if (v === null || v === undefined) return "-";
  if (typeof v !== "number") return String(v);
  if (opts.compact && Math.abs(v) >= 10_000) {
    return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
  }
  const isInt = Number.isInteger(v);
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: isInt ? 0 : 2, maximumFractionDigits: 2 }).format(v);
}

export function formatCell(v: Cell): string {
  if (v === null) return "NULL";
  if (typeof v === "number") return formatNumber(v);
  return String(v);
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

export function timeAgo(epochSeconds: number): string {
  const s = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function toCsv(columns: string[], rows: Cell[][]): string {
  const esc = (v: Cell) => {
    if (v === null) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}

export function download(filename: string, content: string, mime = "text/csv") {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
