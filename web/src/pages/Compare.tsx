import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { scaleLinear, scaleTime } from "d3-scale";
import { curveMonotoneX, line } from "d3-shape";
import { Card, Empty, PageSkeleton, PageTitle } from "@/components/ui";
import { fmt, val } from "@/lib/format";
import { bmFor, useApp, useSeries } from "@/lib/store";

const PALETTE = ["#5eead4", "#a78bfa", "#fbbf24", "#f472b6"];

export default function Compare() {
  const { data } = useApp();
  const series = useSeries(data);
  const ids = useMemo(() => [...series.keys()].sort((a, b) => bmFor(data, a).display_name.localeCompare(bmFor(data, b).display_name)), [series, data]);
  const [picked, setPicked] = useState<string[]>([]);
  if (!data) return <PageSkeleton />;
  if (!ids.length) return <Empty title="Nothing to compare yet" action={<Link to="/" className="text-accent">← Overview</Link>} />;

  const toggle = (id: string) => setPicked((p) => p.includes(id) ? p.filter((x) => x !== id) : p.length >= 4 ? p : [...p, id]);
  const serieses = picked.map((id, i) => ({ id, color: PALETTE[i]!, rs: series.get(id)!, b: bmFor(data, id) }));

  return (
    <div>
      <PageTitle title="Compare" sub="Pick 2–4 biomarkers. Overlay uses % of each reference range so different units can share an axis." />
      <div className="mb-6 flex flex-wrap gap-2">
        {ids.map((id) => {
          const on = picked.includes(id);
          return (
            <button key={id} onClick={() => toggle(id)} disabled={!on && picked.length >= 4}
              className={`rounded-full border px-3 py-1 text-xs transition focus-ring ${on ? "border-accent bg-accent/15 text-ink" : "border-hairline text-ink-muted hover:text-ink"}`}>
              {bmFor(data, id).display_name}
            </button>
          );
        })}
      </div>
      {picked.length < 2 ? <Empty title="Select at least two biomarkers" /> : (
        <>
          <Card className="mb-8 p-4"><Overlay serieses={serieses} /></Card>
          <div className="grid gap-4 sm:grid-cols-2">{serieses.map((s) => <Card key={s.id} className="p-4"><h3 className="mb-2 text-sm font-medium" style={{ color: s.color }}>{s.b.display_name}</h3><Mini rs={s.rs} color={s.color} /></Card>)}</div>
        </>
      )}
    </div>
  );
}

function Overlay({ serieses }: { serieses: { id: string; color: string; rs: ReturnType<typeof useSeries> extends Map<string, infer V> ? V : never; b: ReturnType<typeof bmFor> }[] }) {
  const W = 720, H = 280, m = { t: 12, r: 12, b: 28, l: 40 };
  const all = serieses.flatMap((s) => s.rs.filter((r) => r.collected_at));
  if (!all.length) return null;
  const ts = all.map((r) => new Date(r.collected_at!).getTime());
  const x = scaleTime().domain([new Date(Math.min(...ts)), new Date(Math.max(...ts))]).range([m.l, W - m.r]);
  const y = scaleLinear().domain([-20, 120]).range([H - m.b, m.t]);
  const pct = (r: (typeof all)[0]) => {
    const v = val(r); if (v == null) return null;
    if (r.ref_low != null && r.ref_high != null && r.ref_high !== r.ref_low) return ((v - r.ref_low) / (r.ref_high - r.ref_low)) * 100;
    return 50;
  };
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Normalized overlay">
        {[0, 50, 100].map((t) => <g key={t}><line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} stroke="rgb(var(--color-hairline))" strokeDasharray={t === 0 || t === 100 ? "3 3" : undefined} /><text x={m.l - 6} y={y(t)} dy=".32em" textAnchor="end" className="fill-ink-subtle text-[10px] tabular-nums">{t}%</text></g>)}
        <rect x={m.l} y={y(100)} width={W - m.r - m.l} height={y(0) - y(100)} fill="rgb(var(--color-status-normal) / 0.06)" />
        {serieses.map((s) => {
          const pts = s.rs.map((r) => ({ t: new Date(r.collected_at!), p: pct(r) })).filter((p): p is { t: Date; p: number } => p.p != null);
          const d = line<(typeof pts)[0]>().x((p) => x(p.t)).y((p) => y(p.p)).curve(curveMonotoneX)(pts)!;
          return <g key={s.id}><path d={d} fill="none" stroke={s.color} strokeWidth={2} />{pts.map((p, i) => <circle key={i} cx={x(p.t)} cy={y(p.p)} r={3.5} fill={s.color} />)}</g>;
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-4 text-xs">{serieses.map((s) => <span key={s.id} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: s.color }} />{s.b.display_name}</span>)}</div>
    </div>
  );
}

function Mini({ rs, color }: { rs: ReturnType<typeof useSeries> extends Map<string, infer V> ? V : never; color: string }) {
  const pts = rs.filter((r) => val(r) != null && r.collected_at);
  if (pts.length < 2) return <div className="text-sm text-ink-subtle">{fmt(val(pts[0]!) ?? null)} · single point</div>;
  const W = 320, H = 80;
  const x = scaleLinear().domain([0, pts.length - 1]).range([4, W - 4]);
  const vs = pts.map((r) => val(r)!);
  const y = scaleLinear().domain([Math.min(...vs), Math.max(...vs)]).nice().range([H - 8, 8]);
  const d = line<(typeof pts)[0]>().x((_, i) => x(i)).y((r) => y(val(r)!)).curve(curveMonotoneX)(pts)!;
  return <svg viewBox={`0 0 ${W} ${H}`} className="w-full"><path d={d} fill="none" stroke={color} strokeWidth={1.75} /></svg>;
}
