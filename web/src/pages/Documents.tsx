import { Link } from "react-router-dom";
import { Card, Empty, PageSkeleton, PageTitle, Stagger } from "@/components/ui";
import { Upload } from "@/components/Upload";
import { fmtDate } from "@/lib/format";
import { useApp } from "@/lib/store";

const DOC_STATUS: Record<string, { label: string; cls: string }> = {
  processing: { label: "Processing", cls: "text-ink-muted bg-surface-overlay" },
  needs_review: { label: "Needs review", cls: "text-status-borderline bg-status-borderline/10" },
  confirmed: { label: "Confirmed", cls: "text-status-normal bg-status-normal/10" },
  failed: { label: "Failed", cls: "text-status-out bg-status-out/10" },
};

export default function Documents() {
  const { data } = useApp();
  if (!data) return <PageSkeleton />;
  return (
    <div>
      <PageTitle title="Documents" sub={`${data.docs.length} report${data.docs.length === 1 ? "" : "s"}`} right={<Upload />} />
      {!data.docs.length ? (
        <Empty title="No reports yet" action={<Upload big />}>Upload a PDF or photo to get started. You'll review every extracted value before it becomes part of your record.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.docs.map((d, i) => {
            const st = DOC_STATUS[d.status] ?? DOC_STATUS.processing!;
            const pending = data.pending.filter((r) => r.document_id === d.id).length;
            return (
              <Stagger key={d.id} i={i}>
                <Card className="overflow-hidden">
                  <div className="relative flex h-28 items-end bg-gradient-to-br from-surface-overlay to-surface-raised p-3">
                    <Thumb name={d.original_filename} pages={d.page_count} />
                    <span className={`absolute right-3 top-3 rounded-full px-2 py-0.5 text-[11px] font-medium ${st.cls}`}>{st.label}</span>
                  </div>
                  <div className="space-y-1 p-4">
                    <div className="truncate font-medium" title={d.original_filename}>{d.lab_name ?? d.original_filename}</div>
                    <div className="text-xs text-ink-muted">{fmtDate(d.report_date ?? d.collected_at)} · {d.page_count} page{d.page_count === 1 ? "" : "s"}</div>
                    <div className="flex items-center justify-between pt-2">
                      <span className="text-xs text-ink-subtle">{pending ? `${pending} pending` : d.source_type.replace(/_/g, " ")}</span>
                      {(d.status === "needs_review" || d.status === "confirmed") && (
                        <Link to={`/review/${d.id}`} className="text-sm text-accent hover:underline">{d.status === "needs_review" ? "Review →" : "Re-open →"}</Link>
                      )}
                    </div>
                  </div>
                </Card>
              </Stagger>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Thumb({ name, pages }: { name: string; pages: number }) {
  return (
    <div className="flex items-end gap-1" aria-hidden>
      {Array.from({ length: Math.min(pages, 3) }, (_, i) => (
        <div key={i} className="h-16 w-12 rounded border border-hairline bg-surface shadow-soft" style={{ transform: `translateX(${i * -6}px) rotate(${i * 3 - 3}deg)` }}>
          <div className="h-1.5 bg-accent/40" /><div className="m-1.5 space-y-1">{[0.9, 0.7, 0.8].map((w, j) => <div key={j} className="h-0.5 rounded bg-hairline" style={{ width: `${w * 100}%` }} />)}</div>
        </div>
      ))}
      <span className="sr-only">{name}</span>
    </div>
  );
}
