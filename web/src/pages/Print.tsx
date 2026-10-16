import { useMemo, useState } from "react";
import { Card, Empty, PageSkeleton, PageTitle, StatusChip, Btn } from "@/components/ui";
import { direction, fmt, fmtDate, resultStatus, val } from "@/lib/format";
import { api } from "@/lib/api";
import { bmFor, CATEGORY_ORDER, useApp, useSeries } from "@/lib/store";

export default function Print() {
  const { data, profile } = useApp();
  const series = useSeries(data);
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const all = useMemo(() => [...series.entries()].map(([id, rs]) => ({ id, rs, last: rs[rs.length - 1]!, b: bmFor(data, id, rs[0]) }))
    .sort((a, b) => (CATEGORY_ORDER.indexOf(a.b.category) - CATEGORY_ORDER.indexOf(b.b.category)) || a.b.display_name.localeCompare(b.b.display_name)), [series, data]);
  if (!data || !profile) return <PageSkeleton />;
  if (!data.results.length) return <Empty title="Nothing to export yet" />;
  const sel = picked ?? new Set(all.map((x) => x.id));
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p ?? sel); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const rows = all.filter((x) => sel.has(x.id));

  function downloadLocal(kind: "csv" | "json") {
    if (kind === "json") {
      const blob = new Blob([JSON.stringify({ profile, results: data!.results.filter((r) => r.biomarker_id && sel.has(r.biomarker_id)) }, null, 2)], { type: "application/json" });
      trigger(blob, `labledger-${profile!.id}.json`); return;
    }
    const head = "biomarker,category,date,value,unit,ref_low,ref_high,flag,document_id\n";
    const body = data!.results.filter((r) => r.biomarker_id && sel.has(r.biomarker_id)).map((r) => {
      const b = bmFor(data, r.biomarker_id!);
      return [csv(b.display_name), csv(b.category), r.collected_at ?? "", val(r) ?? "", r.canonical_unit ?? "", r.ref_low ?? "", r.ref_high ?? "", r.flag, r.document_id].join(",");
    }).join("\n");
    trigger(new Blob([head + body], { type: "text/csv" }), `labledger-${profile!.id}.csv`);
  }
  const trigger = (blob: Blob, name: string) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); URL.revokeObjectURL(a.href); };

  return (
    <div>
      <div className="no-print">
        <PageTitle title="Print & export" sub="A clean one-page summary for a doctor visit, plus machine-readable exports."
          right={<div className="flex flex-wrap gap-2">
            <Btn onClick={() => window.print()}>Print</Btn>
            <Btn onClick={() => downloadLocal("csv")}>CSV</Btn>
            <Btn onClick={() => downloadLocal("json")}>JSON</Btn>
            <Btn onClick={() => { window.open(api.exportUrl(profile.id), "_blank"); }} title="Server zip export (JSON + originals)">API export</Btn>
          </div>} />
        <div className="mb-6 flex flex-wrap gap-2">
          <Btn onClick={() => setPicked(new Set(all.map((x) => x.id)))}>Select all</Btn>
          <Btn onClick={() => setPicked(new Set())}>Clear</Btn>
          {all.map((x) => (
            <button key={x.id} onClick={() => toggle(x.id)} className={`rounded-full border px-2.5 py-1 text-xs focus-ring ${sel.has(x.id) ? "border-accent bg-accent/10" : "border-hairline text-ink-muted"}`}>{x.b.display_name}</button>
          ))}
        </div>
      </div>

      <Card className="print-area p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-hairline pb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.14em] text-ink-subtle">Labledger summary</div>
            <h1 className="text-2xl font-semibold tracking-tight">{profile.display_name}</h1>
            <p className="text-sm text-ink-muted">{profile.sex}{profile.dob ? ` · DOB ${profile.dob}` : ""} · printed {fmtDate(new Date().toISOString())}</p>
          </div>
          <div className="text-right text-xs text-ink-subtle">Informational only — not medical advice.</div>
        </div>
        <table className="mt-4 w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wider text-ink-subtle">
            <tr><th className="py-2 pr-3 font-medium">Biomarker</th><th className="py-2 pr-3 font-medium">Latest</th><th className="py-2 pr-3 font-medium">Range</th><th className="py-2 pr-3 font-medium">Status</th><th className="py-2 font-medium">Trend</th></tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {rows.map(({ id, rs, last, b }) => {
              const prev = rs[rs.length - 2]; const a = val(last), p = prev && val(prev);
              return (
                <tr key={id}>
                  <td className="py-2.5 pr-3"><div className="font-medium">{b.display_name}</div><div className="text-xs text-ink-subtle">{b.category}</div></td>
                  <td className="py-2.5 pr-3 tabular-nums">{fmt(a, b.decimals)} {b.canonical_unit}<div className="text-xs text-ink-subtle">{fmtDate(last.collected_at)}</div></td>
                  <td className="py-2.5 pr-3 tabular-nums text-ink-muted">{fmt(last.ref_low, b.decimals)}–{fmt(last.ref_high, b.decimals)}</td>
                  <td className="py-2.5 pr-3"><StatusChip s={resultStatus(last)} dir={direction(last)} /></td>
                  <td className="py-2.5 tabular-nums text-ink-muted">{a != null && p != null ? `${a >= p ? "↑" : "↓"} ${fmt(Math.abs(a - p), b.decimals)} (${rs.length} pts)` : `${rs.length} pts`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
const csv = (s: string) => `"${s.replace(/"/g, '""')}"`;
