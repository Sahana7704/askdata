import React from "react";

export function Icon({ name, className = "", fill = false }: { name: string; className?: string; fill?: boolean }) {
  return <span className={`material-symbols-outlined ${fill ? "icon-fill" : ""} ${className}`} aria-hidden>{name}</span>;
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`bg-surface-container-low border border-outline-variant rounded-lg p-space-md sm:p-space-lg flex flex-col gap-space-md min-w-0 ${className}`}>{children}</section>;
}

export function Pill({ children, tone = "neutral", className = "" }: { children: React.ReactNode; tone?: "neutral" | "teal" | "violet" | "amber" | "red"; className?: string }) {
  // "teal" = success, "violet" = neutral emphasis (kept as names so callers don't change)
  const tones = {
    neutral: "border-outline-variant text-on-surface-variant",
    teal: "border-secondary/40 text-secondary",
    violet: "border-outline text-on-surface",
    amber: "border-tertiary/40 text-tertiary",
    red: "border-error/40 text-error",
  };
  return <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-label-code-sm ${tones[tone]} ${className}`}>{children}</span>;
}

export function Button({ children, onClick, variant = "secondary", disabled, className = "", title, type = "button" }: {
  children: React.ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost"; disabled?: boolean; className?: string; title?: string; type?: "button" | "submit";
}) {
  const v = {
    primary: "bg-primary text-on-primary hover:bg-primary-fixed-dim font-medium",
    secondary: "border border-outline-variant bg-surface-container hover:bg-surface-container-high text-on-surface",
    ghost: "text-on-surface-variant hover:bg-surface-container hover:text-on-surface",
  }[variant];
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled}
      className={`inline-flex items-center justify-center gap-1.5 rounded px-3 py-1.5 text-body-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${v} ${className}`}>
      {children}
    </button>
  );
}

export function Banner({ tone, children }: { tone: "error" | "warn" | "info"; children: React.ReactNode }) {
  const t = { error: "border-error/40 text-error", warn: "border-tertiary/40 text-tertiary", info: "border-outline text-on-surface" }[tone];
  const icon = { error: "error", warn: "warning", info: "info" }[tone];
  return (
    <div className={`flex items-start gap-3 rounded-lg border bg-surface-container-low px-4 py-3 text-body-sm ${t}`} role="alert">
      <Icon name={icon} className="text-xl mt-0.5" />
      <div className="text-on-surface/90">{children}</div>
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: string; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <Icon name={icon} className="text-3xl text-on-surface-variant/60" />
      <div className="text-headline-sm text-on-surface">{title}</div>
      {children && <div className="text-body-sm text-on-surface-variant max-w-md">{children}</div>}
    </div>
  );
}
