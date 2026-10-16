import { Link } from "react-router-dom";
import { RangeBar, Sparkline } from "@/components/charts";
import { Card, Empty, PageSkeleton, PageTitle, Segmented, Stagger, StatusChip } from "@/components/ui";
import { Upload } from "@/components/Upload";
import { direction, fmt, fmtDate, resultStatus, unitScale, val } from "@/lib/format";
import { bmFor, CATEGORY_ORDER, useApp, useSeries } from "@/lib/store";
import type { Result } from "@/lib/types";
import { useState } from "react";

export default function Overview() {
  const { data, profile, altUnits } = useApp();
  const series = useSeries(data);
  const [mode, setMode] = useState<"cards" | "ranges">("cards");
  if (!data) return <PageSkeleton />;
  const first = profile!.display_name.split(" ")[0];
  if (!data.results.length) {
    return (
      <div>
        <PageTitle title={`Hello, ${first}`} />
        <Empty title={data.docs.length ? "Nothing confirmed yet" : "Add your first report"}
          action={data.pending.length ? <Link to="/documents" className="text-accent">Review {data.pending.length} pending values →</Link> : <Upload big />}>
          {data.docs.length ? "Confirm extracted values in review and they'll appear here as trends." : "Upload a PDF or photo of a lab report. You'll review every value before it's saved to your record."}
        </Empty>
      </div>
    );
  }
  const latestDoc = data.docs.find((d) => d.status === "confirmed") ?? data.docs[0];
  const latest = [...series.entries()].map(([id, rs]) => ({ id, rs, last: rs[rs.length - 1]!, prev: rs[rs.length - 2] }));
  const attention = latest.filter((x) => resultStatus(x.last) === "out" || notable(x.last, x.prev));
  const heroRs = latestDoc ? data.results.filter((r) => r.document_id === latestDoc.id) : [];
  const counts = { normal: 0, borderline: 0, out: 0, unknown: 0 };
  heroRs.forEach((r) => counts[resultStatus(r)]++);
  const cats = [...new Set(latest.map((x) => bmFor(data, x.id, x.last).category))].sort((a, b) => rank(a) - rank(b));

  return (
    <div className="space-y-10">
      <PageTitle title={`Hello, ${first}`} sub={`${data.results.length} confirmed values across ${data.docs.length} reports`} right={<Upload />} />

      {data.pending.length > 0 && (
        <Link to="/documents" className="flex items-center justify-between rounded-card border border-status-borderline/40 bg-status-borderline/5 px-4 py-3 text-sm focus-ring">
          <span><span aria-hidden className="mr-2 text-status-borderline">◆</span>{data.pending.length} extracted values are waiting for your review</span><span className="text-accent">Review →</span>
        </Link>
      )}

      {latestDoc && (
        <Stagger>
          <Card className="relative overflow-hidden p-6 sm:p-8">
            <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
            <div className="text-xs uppercase tracking-[0.14em] text-ink-subtle">Latest report</div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">{fmtDate(latestDoc.report_date ?? latestDoc.collected_at, { day: "numeric", month: "long", year: "numeric" })}</h2>
              <span className="text-ink-muted">{latestDoc.lab_name ?? latestDoc.original_filename}</span>
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {([["Tests", heroRs.length, null], ["In range", counts.normal, "normal"], ["Borderline", counts.borderline, "borderline"], ["Out of range", counts.out, "out"]] as const).map(([l, n, s]) => (
                <div key={l}><dt className="flex items-center gap-1.5 text-xs text-ink-subtle">{s && <StatusChip s={s} compact />}{l}</dt><dd className="mt-1 text-3xl font-semibold tabular-nums">{n}</dd></div>
              ))}
            </dl>
          </Card>
        </Stagger>
      )}

      {attention.length > 0 && (
        <section aria-labelledby="att">
          <h2 id="att" className="mb-3 text-sm font-medium uppercase tracking-[0.14em] text-ink-subtle">Attention</h2>
          <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
            {attention.map((x, i) => {
              const b = bmFor(data, x.id, x.last); const u = unitScale(b, altUnits);
              return (
                <Stagger key={x.id} i={i} className="snap-start">
                  <Link to={`/biomarker/${x.id}`} className="block w-56 rounded-card border border-hairline bg-surface-raised/70 p-4 transition hover:border-accent/40 focus-ring">
                    <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{b.display_name}</span><StatusChip s={resultStatus(x.last)} dir={direction(x.last)} compact /></div>
                    <div className="mt-2 text-2xl font-semibold tabular-nums">{fmt(val(x.last)! * u.f, u.decimals)} <span className="text-xs font-normal text-ink-muted">{u.unit}</span></div>
                    <Delta last={x.last} prev={x.prev} f={u.f} d={u.decimals} />
                  </Link>
                </Stagger>
              );
            })}
          </div>
        </section>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-[0.14em] text-ink-subtle">By category</h2>
        <Segmented label="View" value={mode} onChange={setMode} options={[["cards", "Cards"], ["ranges", "Range position"]]} />
      </div>
      {cats.map((cat) => {
        const items = latest.filter((x) => bmFor(data, x.id, x.last).category === cat);
        return (
          <section key={cat} aria-label={cat}>
            <h3 className="mb-3 text-lg font-semibold tracking-tight">{cat}</h3>
            {mode === "cards" ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((x, i) => {
                  const b = bmFor(data, x.id, x.last); const u = unitScale(b, altUnits);
                  return (
                    <Stagger key={x.id} i={i}>
                      <Link to={`/biomarker/${x.id}`} className="group block rounded-card border border-hairline bg-surface-raised/60 p-4 transition hover:-translate-y-0.5 hover:border-accent/40 focus-ring">
                        <div className="flex items-start justify-between gap-2"><span className="text-sm text-ink-muted group-hover:text-ink">{b.display_name}</span><StatusChip s={resultStatus(x.last)} dir={direction(x.last)} /></div>
                        <div className="mt-3 flex items-end justify-between gap-2">
                          <div>
                            <div className="text-2xl font-semibold tabular-nums">{x.last.comparator !== "=" ? x.last.comparator : ""}{val(x.last) != null ? fmt(val(x.last)! * u.f, u.decimals) : x.last.value_qualitative} <span className="text-xs font-normal text-ink-muted">{u.unit}</span></div>
                            <Delta last={x.last} prev={x.prev} f={u.f} d={u.decimals} />
                          </div>
                          <Sparkline rs={x.rs} />
                        </div>
                      </Link>
                    </Stagger>
                  );
                })}
              </div>
            ) : (
              <Card className="divide-y divide-hairline">
                {items.map((x) => {
                  const b = bmFor(data, x.id, x.last); const u = unitScale(b, altUnits);
                  return (
                    <Link key={x.id} to={`/biomarker/${x.id}`} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-surface-overlay/50 sm:grid-cols-[12rem_1fr_7rem]">
                      <span className="truncate text-sm">{b.display_name}</span>
                      <span className="text-right text-sm tabular-nums sm:order-last">{fmt(val(x.last)! * u.f, u.decimals)} <span className="text-xs text-ink-subtle">{u.unit}</span></span>
                      <div className="col-span-2 sm:col-span-1"><RangeBar r={x.last} decimals={b.decimals} /></div>
                    </Link>
                  );
                })}
              </Card>
            )}
          </section>
        );
      })}
    </div>
  );
}

const rank = (c: string) => { const i = CATEGORY_ORDER.indexOf(c); return i < 0 ? 99 : i; };
function notable(last: Result, prev?: Result) {
  const a = val(last), b = prev && val(prev);
  if (a == null || b == null || !b) return false;
  const span = last.ref_high != null && last.ref_low != null ? last.ref_high - last.ref_low : Math.abs(b);
  return Math.abs(a - b) > span * 0.25 || resultStatus(last) !== resultStatus(prev!);
}
export function Delta({ last, prev, f, d }: { last: Result; prev?: Result; f: number; d: number }) {
  const a = val(last), b = prev && val(prev);
  if (a == null || b == null) return <div className="text-xs text-ink-subtle">{fmtDate(last.collected_at)}</div>;
  const diff = (a - b) * f;
  const z = Math.abs(diff) < Math.pow(10, -d) / 2;
  return <div className="text-xs tabular-nums text-ink-subtle"><span className="text-ink-muted">{z ? "→ no change" : `${diff > 0 ? "↑ +" : "↓ −"}${fmt(Math.abs(diff), d)}`}</span> vs {fmtDate(prev!.collected_at, { month: "short", year: "numeric" })}</div>;
}
