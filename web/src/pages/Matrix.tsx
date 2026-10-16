import { Link } from "react-router-dom";
import { statusColor } from "@/components/charts";
import { Empty, PageSkeleton, PageTitle, StatusChip } from "@/components/ui";
import { fmtDate, resultStatus, val } from "@/lib/format";
import { bmFor, CATEGORY_ORDER, useApp, useSeries } from "@/lib/store";
import type { Status } from "@/lib/types";

export default function Matrix() {
  const { data } = useApp();
  const series = useSeries(data);
  if (!data) return <PageSkeleton />;
  if (!data.results.length) return <Empty title="Nothing to matrix yet" action={<Link to="/" className="text-accent">← Overview</Link>} />;

  const dates = [...new Set(data.results.map((r) => (r.collected_at ?? "").slice(0, 10)).filter(Boolean))].sort();
  const rows = [...series.entries()].map(([id, rs]) => ({ id, rs, b: bmFor(data, id, rs[0]) }))
    .sort((a, b) => (CATEGORY_ORDER.indexOf(a.b.category) - CATEGORY_ORDER.indexOf(b.b.category)) || a.b.display_name.localeCompare(b.b.display_name));

  return (
    <div>
      <PageTitle title="Timeline matrix" sub="Biomarkers × report dates. Shape + color encode status."
        right={<div className="flex flex-wrap gap-2">{(["normal", "borderline", "out", "unknown"] as Status[]).map((s) => <StatusChip key={s} s={s} />)}</div>} />
      <div className="overflow-auto rounded-card border border-hairline">
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr className="bg-surface-overlay/60">
              <th className="sticky left-0 z-10 bg-surface-raised px-3 py-2 text-left font-medium text-ink-muted">Biomarker</th>
              {dates.map((d) => <th key={d} className="px-1.5 py-2 font-medium tabular-nums text-ink-subtle whitespace-nowrap">{fmtDate(d, { month: "short", day: "numeric", year: "2-digit" })}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ id, rs, b }) => (
              <tr key={id} className="border-t border-hairline/60 hover:bg-surface-overlay/30">
                <th className="sticky left-0 z-10 bg-surface-raised px-3 py-1.5 text-left font-normal">
                  <Link to={`/biomarker/${id}`} className="hover:text-accent">{b.display_name}</Link>
                  <div className="text-[10px] text-ink-subtle">{b.category}</div>
                </th>
                {dates.map((d) => {
                  const r = rs.find((x) => (x.collected_at ?? "").startsWith(d));
                  if (!r || val(r) == null) return <td key={d} className="px-1.5 py-1.5 text-center text-ink-subtle/40">·</td>;
                  const s = resultStatus(r);
                  return (
                    <td key={d} className="px-1.5 py-1.5 text-center" title={`${b.display_name}: ${val(r)} (${s})`}>
                      <Link to={`/biomarker/${id}`} aria-label={`${b.display_name} ${d} ${s}`}
                        className="inline-block h-3.5 w-3.5" style={{ color: statusColor[s] }}>
                        {s === "out" ? <svg viewBox="0 0 14 14" aria-hidden><path d="M7 1 L13 13 H1 Z" fill="currentColor" /></svg>
                          : s === "borderline" ? <svg viewBox="0 0 14 14" aria-hidden><path d="M7 1 L13 7 L7 13 L1 7 Z" fill="currentColor" /></svg>
                          : s === "unknown" ? <svg viewBox="0 0 14 14" aria-hidden><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
                          : <svg viewBox="0 0 14 14" aria-hidden><circle cx="7" cy="7" r="5" fill="currentColor" /></svg>}
                      </Link>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
