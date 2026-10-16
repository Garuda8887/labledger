import { scaleLinear, scaleTime } from "d3-scale";
import { area, curveMonotoneX, curveStepAfter, line } from "d3-shape";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useRef, useState } from "react";
import { fmt, fmtDate, resultStatus, val } from "@/lib/format";
import type { Result, Status } from "@/lib/types";

const sColor: Record<Status, string> = {
  normal: "rgb(var(--color-status-normal))",
  borderline: "rgb(var(--color-status-borderline))",
  out: "rgb(var(--color-status-out))",
  unknown: "rgb(var(--color-status-unknown))",
};
export const statusColor = sColor;

export function Sparkline({ rs, w = 96, h = 28 }: { rs: Result[]; w?: number; h?: number }) {
  const pts = rs.filter((r) => val(r) != null && r.collected_at);
  if (pts.length < 2) return <div style={{ width: w, height: h }} />;
  const xs = scaleLinear().domain([0, pts.length - 1]).range([2, w - 2]);
  const vs = pts.map((r) => val(r)!);
  const lo = Math.min(...vs, ...pts.map((r) => r.ref_low ?? Infinity));
  const hi = Math.max(...vs, ...pts.map((r) => r.ref_high ?? -Infinity));
  const ys = scaleLinear().domain([lo, hi]).nice().range([h - 3, 3]);
  const d = line<Result>().x((_, i) => xs(i)).y((r) => ys(val(r)!)).curve(curveMonotoneX)(pts)!;
  const last = pts[pts.length - 1]!;
  return (
    <svg width={w} height={h} aria-hidden className="overflow-visible">
      <path d={d} fill="none" stroke="rgb(var(--color-ink-muted))" strokeWidth={1.25} />
      <circle cx={xs(pts.length - 1)} cy={ys(val(last)!)} r={2.5} fill={sColor[resultStatus(last)]} />
    </svg>
  );
}

/** Main time-series with per-result reference band (band shifts when ranges change between labs). */
export function TimeSeries({ rs, scale = 1, decimals = 1, unit, onPick, height = 300 }: { rs: Result[]; scale?: number; decimals?: number; unit: string; onPick?: (r: Result) => void; height?: number }) {
  const reduce = useReducedMotion();
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 720, H = height, m = { t: 16, r: 16, b: 28, l: 44 };
  const pts = useMemo(() => rs.filter((r) => val(r) != null && r.collected_at).map((r) => ({ r, t: new Date(r.collected_at!), v: val(r)! * scale, lo: r.ref_low != null ? r.ref_low * scale : null, hi: r.ref_high != null ? r.ref_high * scale : null })), [rs, scale]);
  if (!pts.length) return <div className="grid h-48 place-items-center text-sm text-ink-subtle">No numeric values to chart</div>;
  const t0 = pts[0]!.t, t1 = pts[pts.length - 1]!.t;
  const x = scaleTime().domain(t0.getTime() === t1.getTime() ? [new Date(+t0 - 864e5 * 30), new Date(+t1 + 864e5 * 30)] : [t0, t1]).range([m.l, W - m.r]);
  const all = pts.flatMap((p) => [p.v, p.lo, p.hi].filter((n): n is number => n != null));
  const y = scaleLinear().domain([Math.min(...all), Math.max(...all)]).nice().range([H - m.b, m.t]);
  const band = area<(typeof pts)[number]>().x((p) => x(p.t)).y0((p) => y(p.lo ?? y.domain()[0]!)).y1((p) => y(p.hi ?? y.domain()[1]!)).curve(curveStepAfter);
  const hasBand = pts.some((p) => p.lo != null || p.hi != null);
  const d = line<(typeof pts)[number]>().x((p) => x(p.t)).y((p) => y(p.v)).curve(curveMonotoneX)(pts)!;
  const hp = hover != null ? pts[hover] : null;

  function move(e: React.PointerEvent) {
    const box = ref.current!.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    let best = 0;
    pts.forEach((p, i) => { if (Math.abs(x(p.t) - px) < Math.abs(x(pts[best]!.t) - px)) best = i; });
    setHover(best);
  }
  function key(e: React.KeyboardEvent) {
    if (e.key === "ArrowRight") setHover((h) => Math.min(pts.length - 1, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? pts.length) - 1));
    else if (e.key === "Enter" && hp) onPick?.(hp.r);
    else return;
    e.preventDefault();
  }
  return (
    <div className="relative">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full touch-none select-none focus-ring rounded-lg" tabIndex={0} role="img"
        aria-label={`Time series with ${pts.length} values. Use arrow keys to scrub, Enter to open source.`}
        onPointerMove={move} onPointerDown={move} onPointerLeave={() => setHover(null)} onKeyDown={key} onClick={() => hp && onPick?.(hp.r)}>
        {y.ticks(5).map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke="rgb(var(--color-hairline))" />
            <text x={m.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-ink-subtle text-[10px] tabular-nums">{fmt(t, Math.max(0, decimals - 1))}</text>
          </g>
        ))}
        {x.ticks(Math.min(6, pts.length + 1)).map((t) => (
          <text key={+t} x={x(t)} y={H - 8} textAnchor="middle" className="fill-ink-subtle text-[10px]">{t.toLocaleDateString(undefined, { month: "short", year: "2-digit" })}</text>
        ))}
        {hasBand && <path d={band(pts)!} fill="rgb(var(--color-status-normal) / 0.09)" stroke="rgb(var(--color-status-normal) / 0.35)" strokeDasharray="3 3" />}
        <motion.path d={d} fill="none" stroke="rgb(var(--color-accent))" strokeWidth={2} strokeLinecap="round"
          initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, ease: "easeInOut" }} />
        {hp && <line x1={x(hp.t)} x2={x(hp.t)} y1={m.t} y2={H - m.b} stroke="rgb(var(--color-ink-subtle))" strokeDasharray="2 3" />}
        {pts.map((p, i) => {
          const s = resultStatus(p.r);
          const big = i === hover;
          return s === "out"
            ? <path key={p.r.id} d={`M${x(p.t)},${y(p.v) - (big ? 7 : 5)} l${big ? 6 : 4.5},${big ? 10 : 8} h-${big ? 12 : 9} z`} fill={sColor[s]} className="cursor-pointer" />
            : <circle key={p.r.id} cx={x(p.t)} cy={y(p.v)} r={big ? 6 : 4} fill="rgb(var(--color-surface-raised))" stroke={sColor[s]} strokeWidth={2} className="cursor-pointer" />;
        })}
      </svg>
      {hp && (
        <div className="pointer-events-none absolute top-2 rounded-lg border border-hairline bg-surface-overlay/95 px-3 py-2 text-xs shadow-soft backdrop-blur"
          style={{ left: `${Math.min(70, Math.max(2, (x(hp.t) / W) * 100 - 10))}%` }}>
          <div className="text-ink-muted">{fmtDate(hp.r.collected_at)}</div>
          <div className="text-base font-semibold tabular-nums">{hp.r.comparator !== "=" ? hp.r.comparator : ""}{fmt(hp.v, decimals)} <span className="text-xs font-normal text-ink-muted">{unit}</span></div>
          <div className="tabular-nums text-ink-subtle">Range {fmt(hp.lo, decimals)}–{fmt(hp.hi, decimals)}</div>
          {onPick && <div className="mt-1 text-accent">Click to open source ↗</div>}
        </div>
      )}
    </div>
  );
}

/** Bullet bar: where the latest value sits in its reference range. */
export function RangeBar({ r, decimals = 1 }: { r: Result; decimals?: number }) {
  const v = val(r);
  const lo = r.ref_low, hi = r.ref_high;
  if (v == null || (lo == null && hi == null)) return <div className="h-2 rounded-full bg-hairline/60" title="No reference range" />;
  const L = lo ?? 0, Hh = hi ?? L * 2;
  const span = Hh - L || Math.abs(L) || 1;
  const min = Math.min(L - span * 0.5, v), max = Math.max(Hh + span * 0.5, v);
  const p = (n: number) => ((n - min) / (max - min)) * 100;
  const s = resultStatus(r);
  return (
    <div className="relative h-5" role="img" aria-label={`Value ${fmt(v, decimals)}, range ${fmt(lo, decimals)} to ${fmt(hi, decimals)}`}>
      <div className="absolute inset-x-0 top-2 h-1 rounded-full bg-hairline" />
      <div className="absolute top-1.5 h-2 rounded-full bg-status-normal/30 ring-1 ring-status-normal/40" style={{ left: `${p(L)}%`, width: `${p(Hh) - p(L)}%` }} />
      <div className="absolute top-0 h-5 w-[3px] -translate-x-1/2 rounded-full" style={{ left: `${p(v)}%`, background: sColor[s] }} />
    </div>
  );
}
