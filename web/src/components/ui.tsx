import { motion, useReducedMotion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Status } from "@/lib/types";

const STATUS: Record<Status, { label: string; icon: string; cls: string }> = {
  normal: { label: "In range", icon: "●", cls: "text-status-normal bg-status-normal/10 ring-status-normal/30" },
  borderline: { label: "Borderline", icon: "◆", cls: "text-status-borderline bg-status-borderline/10 ring-status-borderline/30" },
  out: { label: "Out of range", icon: "▲", cls: "text-status-out bg-status-out/10 ring-status-out/30" },
  unknown: { label: "No range", icon: "○", cls: "text-status-unknown bg-status-unknown/10 ring-status-unknown/30" },
};
export const statusMeta = STATUS;

/** Status always conveyed by shape + label, never color alone. */
export function StatusChip({ s, dir, compact }: { s: Status; dir?: "low" | "high" | null; compact?: boolean }) {
  const m = STATUS[s];
  const label = s === "out" && dir ? (dir === "low" ? "Low" : "High") : m.label;
  const icon = s === "out" && dir === "low" ? "▼" : m.icon;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${m.cls}`} title={label}>
      <span aria-hidden className="text-[9px] leading-none">{icon}</span>
      {compact ? <span className="sr-only">{label}</span> : label}
    </span>
  );
}

export function Card({ children, className = "", as: As = "div" }: { children: ReactNode; className?: string; as?: "div" | "section" | "article" }) {
  return <As className={`rounded-card border border-hairline bg-surface-raised/70 backdrop-blur-sm ${className}`}>{children}</As>;
}

export function Btn({ variant = "ghost", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const v = {
    primary: "bg-accent text-surface hover:bg-accent/90",
    ghost: "border border-hairline text-ink hover:bg-surface-overlay",
    danger: "border border-status-out/40 text-status-out hover:bg-status-out/10",
  }[variant];
  return <button className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 focus-ring ${v} ${className}`} {...p} />;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-lg ${className}`} aria-hidden />;
}
export function PageSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-36" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-32" />)}</div>
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden className="text-accent/70">
        <rect x="10" y="6" width="36" height="44" rx="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M17 34 l7 -8 l6 5 l9 -11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M17 42 h22" stroke="currentColor" strokeOpacity=".4" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {children && <div className="max-w-md text-sm text-ink-muted">{children}</div>}
      {action}
    </Card>
  );
}

export function PageTitle({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {sub && <p className="mt-1 text-sm text-ink-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Stagger({ children, i = 0, className = "" }: { children: ReactNode; i?: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: reduce ? 0 : Math.min(i, 12) * 0.035, ease: [0.2, 0.7, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: [T, string][]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-hairline p-0.5 text-xs">
      {options.map(([v, l]) => (
        <button key={v} role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={`rounded-md px-2.5 py-1 transition-colors focus-ring ${value === v ? "bg-surface-overlay text-ink" : "text-ink-muted hover:text-ink"}`}>{l}</button>
      ))}
    </div>
  );
}
