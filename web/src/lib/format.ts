import type { Biomarker, Result, Status } from "./types";

export function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
export function fmtDate(d: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  if (!d) return "—";
  const t = new Date(d);
  return Number.isNaN(t.getTime()) ? "—" : t.toLocaleDateString(undefined, opts);
}
export function val(r: Result): number | null {
  return r.normalized_value ?? r.value_numeric;
}
/** Status from value vs range. Borderline = within 5% of range span of a bound. */
export function statusOf(r: Pick<Result, "flag" | "ref_low" | "ref_high"> & { v: number | null }): Status {
  const { v, ref_low: lo, ref_high: hi } = r;
  if (v == null) return r.flag === "normal" ? "normal" : r.flag === "unknown" ? "unknown" : "out";
  if (lo == null && hi == null) return r.flag === "low" || r.flag === "high" ? "out" : r.flag === "normal" ? "normal" : "unknown";
  if ((lo != null && v < lo) || (hi != null && v > hi)) return "out";
  if (lo != null && hi != null) {
    const m = (hi - lo) * 0.05;
    if (v - lo < m || hi - v < m) return "borderline";
  }
  return "normal";
}
export const resultStatus = (r: Result) => statusOf({ ...r, v: val(r) });
export function direction(r: Result): "low" | "high" | null {
  const v = val(r);
  if (v == null) return r.flag === "low" || r.flag === "high" ? r.flag : null;
  if (r.ref_low != null && v < r.ref_low) return "low";
  if (r.ref_high != null && v > r.ref_high) return "high";
  return null;
}
export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("") || "?";
}
export function unitScale(b: Biomarker | undefined, alt: boolean) {
  if (!b || !alt || !b.alt_unit || !b.alt_factor) return { f: 1, unit: b?.canonical_unit ?? "", decimals: b?.decimals ?? 1 };
  const f = b.alt_factor;
  const decimals = Math.max(0, Math.min(3, Math.round((b.decimals ?? 1) - Math.log10(f))));
  return { f, unit: b.alt_unit, decimals };
}
export const sortByDate = (a: Result, b: Result) => (a.collected_at ?? "").localeCompare(b.collected_at ?? "");
