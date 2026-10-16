import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Sparkline, statusColor } from "@/components/charts";
import { Card, Empty, PageSkeleton, PageTitle, Segmented, Stagger, StatusChip } from "@/components/ui";
import { direction, fmt, fmtDate, resultStatus, val } from "@/lib/format";
import { bmFor, CATEGORY_ORDER, useApp, useSeries } from "@/lib/store";
import type { Result, Status } from "@/lib/types";

const STATUSES: Status[] = ["normal", "borderline", "out", "unknown"];
const LABEL: Record<Status, string> = { normal: "In range", borderline: "Borderline", out: "Out of range", unknown: "No range" };
const SEVERITY: Record<Status, number> = { out: 3, borderline: 2, normal: 1, unknown: 0 };

/** Signed % distance beyond the nearest bound (low = negative). null when in range / no range. */
function deviation(r: Result): number | null {
  const v = val(r);
  if (v == null) return null;
  const { ref_low: lo, ref_high: hi } = r;
  if (hi != null && v > hi) return ((v - hi) / (Math.abs(hi) || 1)) * 100;
  if (lo != null && v < lo) return ((v - lo) / (Math.abs(lo) || 1)) * 100;
  return null;
}
function pctChange(last: Result, prev?: Result): number | null {
  const a = val(last);
  const b = prev ? val(prev) : null;
  return a == null || b == null || b === 0 ? null : ((a - b) / Math.abs(b)) * 100;
}
function rangeText(r: Result): string {
  const { ref_low: lo, ref_high: hi } = r;
  return lo != null && hi != null ? `${lo} – ${hi}` : hi != null ? `< ${hi}` : `> ${lo}`;
}
const rank = (c: string) => { const i = CATEGORY_ORDER.indexOf(c); return i < 0 ? 99 : i; };
const emptyCounts = (): Record<Status, number> => ({ normal: 0, borderline: 0, out: 0, unknown: 0 });
const total = (c: Record<Status, number>) => STATUSES.reduce((n, s) => n + c[s], 0);
const summary = (c: Record<Status, number>) => STATUSES.map((s) => `${c[s]} ${LABEL[s]}`).join(", ");

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-muted">
      {STATUSES.map((s) => <span key={s} className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-sm" style={{ background: statusColor[s] }} />{LABEL[s]}</span>)}
    </div>
  );
}

function Panel({ title, sub, children, right }: { title: string; sub?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div><h2 className="text-sm font-semibold">{title}</h2>{sub && <p className="mt-0.5 text-xs text-ink-muted">{sub}</p>}</div>
        {right}
      </div>
      {children}
    </Card>
  );
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: Status }) {
  return (
    <Card className="p-4">
      <div className="text-[11px] uppercase tracking-wider text-ink-subtle">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums" style={tone ? { color: statusColor[tone] } : undefined}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-muted">{sub}</div>}
    </Card>
  );
}

/** One row of a diverging bar chart: negative extends left of the centre line, positive right. */
function DivergingRow({ id, name, v, max, color, label }: { id: string; name: string; v: number; max: number; color: string; label: string }) {
  const neg = v < 0;
  return (
    <li className="grid grid-cols-[7.5rem_1fr] items-center gap-3 text-xs">
      <Link to={`/biomarker/${id}`} className="truncate hover:text-accent">{name}</Link>
      <div className="relative flex h-5 items-center">
        <span className="absolute left-1/2 top-0 h-full w-px bg-hairline" />
        <span className="absolute h-4 rounded-sm" style={{ background: color, [neg ? "right" : "left"]: "50%", width: `${(Math.abs(v) / max) * 48}%` }} />
        <span className="absolute tabular-nums text-ink-muted" style={neg ? { left: "52%" } : { right: "52%" }}>{label}</span>
      </div>
    </li>
  );
}

export default function Analysis() {
  const { data } = useApp();
  const series = useSeries(data);
  const [sort, setSort] = useState<"status" | "category" | "change">("status");

  const a = useMemo(() => {
    if (!data) return null;
    const rows = [...series.entries()].map(([id, rs]) => {
      const last = rs[rs.length - 1]!;
      const prev = rs[rs.length - 2];
      return { id, rs, last, b: bmFor(data, id, last), status: resultStatus(last), dev: deviation(last), chg: pctChange(last, prev) };
    });
    const counts = emptyCounts();
    const byCat = new Map<string, Record<Status, number>>();
    rows.forEach((r) => {
      counts[r.status]++;
      const c = byCat.get(r.b.category) ?? emptyCounts();
      c[r.status]++;
      byCat.set(r.b.category, c);
    });
    const byDate = new Map<string, Record<Status, number>>();
    data.results.forEach((r) => {
      const d = (r.collected_at ?? "").slice(0, 10);
      if (!d) return;
      const c = byDate.get(d) ?? emptyCounts();
      c[resultStatus(r)]++;
      byDate.set(d, c);
    });
    return {
      rows, counts,
      byCat: [...byCat.entries()].sort((x, y) => rank(x[0]) - rank(y[0])),
      byDate: [...byDate.entries()].sort((x, y) => x[0].localeCompare(y[0])),
    };
  }, [data, series]);

  if (!data || !a) return <PageSkeleton />;
  if (!data.results.length) {
    return <Empty title="Nothing to analyse yet" action={<Link to="/" className="text-accent">← Overview</Link>}>Confirm some extracted values and the analysis will appear here.</Empty>;
  }

  const { rows, counts, byCat, byDate } = a;
  const ranged = counts.normal + counts.borderline + counts.out;
  const inPct = ranged ? Math.round((counts.normal / ranged) * 100) : 0;
  const deviants = rows.filter((r) => r.dev != null).sort((x, y) => Math.abs(y.dev!) - Math.abs(x.dev!)).slice(0, 10);
  const maxDev = Math.max(1, ...deviants.map((r) => Math.abs(r.dev!)));
  const movers = rows.filter((r) => r.chg != null).sort((x, y) => Math.abs(y.chg!) - Math.abs(x.chg!)).slice(0, 8);
  const maxChg = Math.max(1, ...movers.map((r) => Math.abs(r.chg!)));
  const maxDay = Math.max(1, ...byDate.map(([, c]) => total(c)));
  const sorted = [...rows].sort((x, y) =>
    sort === "category" ? rank(x.b.category) - rank(y.b.category) || x.b.display_name.localeCompare(y.b.display_name)
    : sort === "change" ? Math.abs(y.chg ?? 0) - Math.abs(x.chg ?? 0)
    : SEVERITY[y.status] - SEVERITY[x.status] || Math.abs(y.dev ?? 0) - Math.abs(x.dev ?? 0));

  return (
    <div className="space-y-6">
      <PageTitle title="Analysis" sub="Where you stand on the latest reading of every tracked marker, and how that has moved over time." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stagger i={0}><Kpi label="Markers tracked" value={String(rows.length)} sub={`${data.results.length} values · ${data.docs.length} reports`} /></Stagger>
        <Stagger i={1}><Kpi label="In range" value={`${inPct}%`} sub={`${counts.normal} of ${ranged} with a range`} tone="normal" /></Stagger>
        <Stagger i={2}><Kpi label="Borderline" value={String(counts.borderline)} sub="within 5% of a limit" tone="borderline" /></Stagger>
        <Stagger i={3}><Kpi label="Out of range" value={String(counts.out)} sub="latest reading" tone="out" /></Stagger>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Status by category" sub="Latest value of each marker" right={<Legend />}>
          <ul className="space-y-3">
            {byCat.map(([cat, c]) => {
              const n = total(c);
              return (
                <li key={cat} className="grid grid-cols-[7.5rem_1fr_2rem] items-center gap-3 text-xs">
                  <span className="truncate text-ink-muted">{cat}</span>
                  <span className="flex h-5 overflow-hidden rounded-md bg-surface-overlay" role="img" aria-label={`${cat}: ${summary(c)}`}>
                    {STATUSES.map((s) => c[s] > 0 && (
                      <span key={s} className="grid place-items-center text-[10px] font-semibold text-black/70" style={{ width: `${(c[s] / n) * 100}%`, background: statusColor[s] }}>{c[s]}</span>
                    ))}
                  </span>
                  <span className="text-right tabular-nums text-ink-subtle">{n}</span>
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel title="Status over time" sub="Values per report date, by status" right={<Legend />}>
          <div className="flex h-44 items-end gap-1.5">
            {byDate.map(([d, c]) => (
              <div key={d} className="flex h-full min-w-0 flex-1 flex-col justify-end" title={`${fmtDate(d)} — ${summary(c)}`}>
                <div className="flex flex-col-reverse overflow-hidden rounded-t" style={{ height: `${(total(c) / maxDay) * 100}%` }}>
                  {STATUSES.map((s) => c[s] > 0 && <span key={s} style={{ flex: c[s], background: statusColor[s] }} />)}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-1.5 flex gap-1.5 text-[10px] text-ink-subtle">
            {byDate.map(([d], i) => <span key={d} className="min-w-0 flex-1 truncate text-center">{byDate.length > 8 && i % 2 ? "" : fmtDate(d, { month: "short", year: "2-digit" })}</span>)}
          </div>
        </Panel>

        <Panel title="Furthest from range" sub="% beyond the nearest limit · low ◀ ▶ high">
          {deviants.length === 0 ? <p className="text-sm text-ink-muted">Every marker with a range is inside it.</p> : (
            <ul className="space-y-2">
              {deviants.map((r) => <DivergingRow key={r.id} id={r.id} name={r.b.display_name} v={r.dev!} max={maxDev} color={statusColor[r.status]} label={`${r.dev! > 0 ? "+" : ""}${fmt(r.dev, 0)}%`} />)}
            </ul>
          )}
        </Panel>

        <Panel title="Biggest movers" sub="% change vs the previous reading · colour = current status">
          {movers.length === 0 ? <p className="text-sm text-ink-muted">Needs at least two readings of a marker.</p> : (
            <ul className="space-y-2">
              {movers.map((r) => <DivergingRow key={r.id} id={r.id} name={r.b.display_name} v={r.chg!} max={maxChg} color={statusColor[r.status]} label={`${r.chg! > 0 ? "▲ +" : "▼ "}${fmt(r.chg, 1)}%`} />)}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="All markers" sub="Latest reading, reference range and trend"
        right={<Segmented label="Sort" value={sort} onChange={setSort} options={[["status", "Status"], ["category", "Category"], ["change", "Change"]]} />}>
        <div className="-mx-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-ink-subtle">
                <th className="px-2 py-2 font-medium">Marker</th><th className="px-2 py-2 font-medium">Latest</th><th className="hidden px-2 py-2 font-medium sm:table-cell">Range</th>
                <th className="px-2 py-2 font-medium">Status</th><th className="hidden px-2 py-2 text-right font-medium sm:table-cell">Change</th><th className="hidden px-2 py-2 font-medium sm:table-cell">Trend</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className="border-t border-hairline/60 hover:bg-surface-overlay/30">
                  <td className="px-2 py-2"><Link to={`/biomarker/${r.id}`} className="hover:text-accent">{r.b.display_name}</Link><div className="text-[10px] text-ink-subtle">{r.b.category}</div></td>
                  <td className="px-2 py-2 tabular-nums">{fmt(val(r.last), r.b.decimals)} <span className="text-xs text-ink-subtle">{r.last.canonical_unit}</span></td>
                  <td className="hidden px-2 py-2 tabular-nums text-ink-muted sm:table-cell">{r.last.ref_low == null && r.last.ref_high == null ? "—" : rangeText(r.last)}</td>
                  <td className="px-2 py-2"><StatusChip s={r.status} dir={direction(r.last)} /></td>
                  <td className="hidden px-2 py-2 text-right tabular-nums text-ink-muted sm:table-cell">{r.chg == null ? "—" : `${r.chg > 0 ? "+" : ""}${fmt(r.chg, 1)}%`}</td>
                  <td className="hidden px-2 py-2 sm:table-cell"><Sparkline rs={r.rs} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
