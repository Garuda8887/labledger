import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TimeSeries } from "@/components/charts";
import { Card, Empty, PageSkeleton, PageTitle, StatusChip } from "@/components/ui";
import { direction, fmt, fmtDate, resultStatus, unitScale, val } from "@/lib/format";
import { bmFor, useApp, useSeries } from "@/lib/store";
import { Delta } from "./Overview";

export default function Biomarker() {
  const { id = "" } = useParams();
  const { data, altUnits, setAltUnits } = useApp();
  const series = useSeries(data);
  const nav = useNavigate();
  const rs = series.get(id) ?? [];
  const last = rs[rs.length - 1];
  const b = bmFor(data, id, last);
  const u = unitScale(b, altUnits);
  const [show, setShow] = useState(false);
  const stats = useMemo(() => {
    const vs = rs.map(val).filter((n): n is number => n != null);
    if (!vs.length) return null;
    return { min: Math.min(...vs), max: Math.max(...vs), avg: vs.reduce((a, c) => a + c, 0) / vs.length, n: vs.length };
  }, [rs]);

  if (!data) return <PageSkeleton />;
  if (!last) return <Empty title="No data for this biomarker" action={<Link to="/" className="text-accent">← Overview</Link>} />;

  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-4 text-sm text-ink-muted hover:text-ink">← Back</button>
      <PageTitle title={b.display_name} sub={b.category}
        right={b.alt_unit ? (
          <button onClick={() => setAltUnits(!altUnits)} className="rounded-lg border border-hairline px-3 py-1.5 text-xs focus-ring" aria-pressed={altUnits}>
            Unit: {u.unit} {altUnits ? `(${b.canonical_unit})` : b.alt_unit ? `(${b.alt_unit})` : ""}
          </button>
        ) : undefined} />

      <div className="mb-6 flex flex-wrap items-end gap-6">
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-subtle">Latest</div>
          <div className="mt-1 flex items-baseline gap-3">
            <span className="text-4xl font-semibold tabular-nums sm:text-5xl">{fmt(val(last)! * u.f, u.decimals)}</span>
            <span className="text-ink-muted">{u.unit}</span>
            <StatusChip s={resultStatus(last)} dir={direction(last)} />
          </div>
          <div className="mt-1 text-sm text-ink-muted">{fmtDate(last.collected_at)} · range {fmt(last.ref_low != null ? last.ref_low * u.f : null, u.decimals)}–{fmt(last.ref_high != null ? last.ref_high * u.f : null, u.decimals)}</div>
          <Delta last={last} prev={rs[rs.length - 2]} f={u.f} d={u.decimals} />
        </div>
        {stats && (
          <dl className="flex flex-wrap gap-6 text-sm">
            {([["Min", stats.min], ["Max", stats.max], ["Avg", stats.avg], ["n", stats.n]] as const).map(([k, v]) => (
              <div key={k}><dt className="text-xs text-ink-subtle">{k}</dt><dd className="tabular-nums font-medium">{k === "n" ? v : fmt(v * u.f, u.decimals)}</dd></div>
            ))}
            <div><dt className="text-xs text-ink-subtle">Trend</dt><dd>{trend(rs)}</dd></div>
          </dl>
        )}
      </div>

      <Card className="p-2 sm:p-4">
        <TimeSeries rs={rs} scale={u.f} decimals={u.decimals} unit={u.unit} onPick={(r) => nav(`/review/${r.document_id}?row=${r.id}`)} />
      </Card>

      <div className="mt-8 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-[0.14em] text-ink-subtle">All values</h2>
        <button className="text-xs text-accent md:hidden" onClick={() => setShow((s) => !s)}>{show ? "Hide" : "Show"} table</button>
      </div>
      <div className={`mt-3 overflow-x-auto ${show ? "block" : "hidden md:block"}`}>
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="text-xs uppercase tracking-wider text-ink-subtle"><tr><th className="py-2 pr-4 font-medium">Date</th><th className="py-2 pr-4 font-medium">Value</th><th className="py-2 pr-4 font-medium">Range</th><th className="py-2 pr-4 font-medium">Status</th><th className="py-2 font-medium">Source</th></tr></thead>
          <tbody className="divide-y divide-hairline">
            {[...rs].reverse().map((r) => (
              <tr key={r.id} className="hover:bg-surface-overlay/40">
                <td className="py-2.5 pr-4 tabular-nums whitespace-nowrap">{fmtDate(r.collected_at)}</td>
                <td className="py-2.5 pr-4 tabular-nums font-medium">{r.comparator !== "=" ? r.comparator : ""}{fmt(val(r)! * u.f, u.decimals)} <span className="text-xs text-ink-subtle">{u.unit}</span></td>
                <td className="py-2.5 pr-4 tabular-nums text-ink-muted">{fmt(r.ref_low != null ? r.ref_low * u.f : null, u.decimals)}–{fmt(r.ref_high != null ? r.ref_high * u.f : null, u.decimals)}</td>
                <td className="py-2.5 pr-4"><StatusChip s={resultStatus(r)} dir={direction(r)} /></td>
                <td className="py-2.5"><Link to={`/review/${r.document_id}?row=${r.id}`} className="text-accent hover:underline">p.{r.page}</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function trend(rs: ReturnType<typeof useSeries> extends Map<string, infer V> ? V : never) {
  if (rs.length < 2) return "—";
  const a = val(rs[0]!), b = val(rs[rs.length - 1]!);
  if (a == null || b == null) return "—";
  const d = b - a;
  if (Math.abs(d) < Math.abs(a) * 0.02) return "Stable →";
  return d > 0 ? "Rising ↑" : "Falling ↓";
}
