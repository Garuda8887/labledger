import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PageImage } from "@/components/PageImage";
import { Btn, Card, Empty, PageSkeleton, StatusChip } from "@/components/ui";
import { api } from "@/lib/api";
import { direction, fmt, fmtDate, resultStatus } from "@/lib/format";
import { useApp } from "@/lib/store";
import type { Biomarker, Doc, Result } from "@/lib/types";

const HIGH = 0.85;

export default function Review() {
  const { id = "" } = useParams();
  const [sp] = useSearchParams();
  const { data, reloadData } = useApp();
  const nav = useNavigate();
  const [rows, setRows] = useState<Result[] | null>(null);
  const [sel, setSel] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [picker, setPicker] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const baseDoc = data?.docs.find((d) => d.id === id);
  const [docOverride, setDocOverride] = useState<Doc | null>(null);
  const doc = docOverride && docOverride.id === id ? docOverride : baseDoc;
  /** ids of previously-confirmed results superseded ("keep new") during this session */
  const [superseded, setSuperseded] = useState<Set<string>>(() => new Set());
  const confirmed = useMemo(() => (data?.results ?? []).filter((r) => !superseded.has(r.id)), [data, superseded]);

  useEffect(() => {
    if (!data) return;
    let live = true;
    api.results({ profile_id: data.docs.find((d) => d.id === id)?.profile_id ?? "", document_id: id })
      .then((rs) => {
        if (!live) return;
        const sorted = rs.filter((r) => r.status !== "rejected").sort((a, b) => a.confidence - b.confidence || a.page - b.page);
        setRows(sorted);
        const want = sp.get("row");
        const i = want ? sorted.findIndex((r) => r.id === want) : 0;
        setSel(Math.max(0, i));
        if (sorted[i >= 0 ? i : 0]) setPage(sorted[i >= 0 ? i : 0]!.page);
      })
      .catch(() => setRows([]));
    return () => { live = false; };
  }, [id, data, sp]);

  const row = rows?.[sel];
  useEffect(() => { if (row) setPage(row.page); }, [row]);

  /** §6.10 duplicate detection: confirmed results with same profile + biomarker + collection day. */
  const conflictsById = useMemo(() => {
    const m = new Map<string, Result[]>();
    rows?.forEach((r) => {
      if (!r.biomarker_id || !r.collected_at) return;
      const day = r.collected_at.slice(0, 10);
      const hits = confirmed.filter((c) => c.id !== r.id && c.profile_id === r.profile_id && c.biomarker_id === r.biomarker_id && c.collected_at?.startsWith(day));
      if (hits.length) m.set(r.id, hits);
    });
    return m;
  }, [rows, confirmed]);
  const conflicts = row ? conflictsById.get(row.id) ?? [] : [];

  // Rows with an unresolved duplicate need an explicit keep-one/keep-both choice, so bulk confirm skips them.
  const highIds = useMemo(() => rows?.filter((r) => r.confidence >= HIGH && r.status === "pending_review" && !conflictsById.has(r.id)).map((r) => r.id) ?? [], [rows, conflictsById]);

  const patch = useCallback(async (r: Result, p: Partial<Result>) => {
    setBusy(true); setMsg(null);
    try {
      const updated = await api.updateResult(r.id, p);
      setRows((xs) => xs!.map((x) => (x.id === r.id ? { ...x, ...updated, ...p } : x)));
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  }, []);

  const dropRow = (r: Result) => setRows((xs) => {
    const next = xs!.filter((x) => x.id !== r.id);
    setSel((s) => Math.min(s, Math.max(0, next.length - 1)));
    return next;
  });
  const confirmOne = async (r: Result) => {
    // PATCH /results ignores `status`; the confirm endpoint is the only real-mode path.
    setBusy(true); setMsg(null);
    try { await api.confirm(r.id); } catch (e) { setMsg((e as Error).message); setBusy(false); return; }
    setBusy(false);
    dropRow(r);
  };
  const rejectOne = async (r: Result) => {
    try { await api.reject(r.id); } catch (e) { setMsg((e as Error).message); return; }
    dropRow(r);
  };
  const confirmHigh = async () => {
    setBusy(true);
    try {
      await api.bulkConfirm(highIds);
      setRows((xs) => xs!.filter((r) => !highIds.includes(r.id) || r.status === "confirmed").map((r) => highIds.includes(r.id) ? { ...r, status: "confirmed" as const } : r).filter((r) => r.status !== "confirmed"));
      setSel(0);
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  };
  /** Duplicate resolution (§6.10). "new" = confirm new + reject (supersede) existing; "existing" = reject new; "both" = confirm new only. */
  const resolveConflict = async (r: Result, keep: "new" | "existing" | "both", existing: Result[]) => {
    setBusy(true); setMsg(null);
    try {
      if (keep === "existing") await api.reject(r.id);
      else {
        await api.confirm(r.id);
        if (keep === "new") {
          await Promise.all(existing.map((c) => api.reject(c.id)));
          setSuperseded((s) => new Set([...s, ...existing.map((c) => c.id)]));
        }
      }
      dropRow(r);
      setMsg(null);
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  };
  const finish = () => { reloadData(); nav("/documents"); };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!rows?.length) return;
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || picker) return;
      if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); setSel((s) => Math.min(rows.length - 1, s + 1)); }
      else if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
      else if (e.key === "Enter" && row && row.status === "pending_review") {
        e.preventDefault();
        if (conflicts.length) setMsg("This row duplicates an existing result — choose keep new, keep existing or keep both.");
        else void confirmOne(row);
      }
      else if (e.key === "Backspace" && row) { e.preventDefault(); void rejectOne(row); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!data) return <PageSkeleton />;
  if (!doc) return <Empty title="Document not found" action={<Link to="/documents" className="text-accent">← Documents</Link>} />;
  if (!rows) return <PageSkeleton />;

  const imgUrl = api.pageImageUrl(doc.id, page);
  const bbox = row?.bbox;

  return (
    <div className="flex flex-col gap-4 lg:h-[calc(100vh-8rem)] lg:flex-row">
      {/* Source pane */}
      <Card className="relative flex min-h-[40vh] flex-1 flex-col overflow-hidden lg:min-h-0">
        <div className="flex flex-wrap items-center gap-2 border-b border-hairline px-3 py-2 text-xs">
          <span className="truncate font-medium">{doc.lab_name ?? doc.original_filename}</span>
          <span className="text-ink-subtle">{fmtDate(doc.report_date ?? doc.collected_at)}</span>
          <DocMetaEditor doc={doc} onSaved={(d) => { setDocOverride(d); reloadData(); }} />
          <div className="ml-auto flex items-center gap-1">
            <Btn onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>‹</Btn>
            <span className="tabular-nums px-1">{page}/{doc.page_count}</span>
            <Btn onClick={() => setPage((p) => Math.min(doc.page_count, p + 1))} disabled={page >= doc.page_count}>›</Btn>
            <Btn onClick={() => setZoom((z) => Math.min(3, z + 0.25))}>+</Btn>
            <Btn onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>−</Btn>
          </div>
        </div>
        <div className="relative flex-1 overflow-auto bg-surface">
          <div className="relative mx-auto origin-top" style={{ width: `${zoom * 100}%`, maxWidth: `${zoom * 640}px` }}>
            {imgUrl ? (
              <PageImage src={imgUrl} bbox={row?.page === page ? bbox : null} sourceType={doc.source_type} label={`Page ${page}`}
                fallback={<PlaceholderPage page={page} />} />
            ) : (
              <PlaceholderPage page={page} highlight={row?.page === page ? bbox : null} row={row} />
            )}
          </div>
        </div>
      </Card>

      {/* Rows pane */}
      <div className="flex w-full flex-col lg:w-[28rem] xl:w-[32rem]">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold tracking-tight">Review</h1>
          <span className="text-xs text-ink-subtle">{rows.length} pending · sorted by confidence{conflictsById.size > 0 && <> · <span className="text-status-borderline">↔ {conflictsById.size} duplicate{conflictsById.size > 1 ? "s" : ""}</span></>}</span>
          <div className="ml-auto flex gap-2">
            {highIds.length > 0 && <Btn variant="primary" disabled={busy} onClick={() => void confirmHigh()}>Confirm {highIds.length} high-conf</Btn>}
            <Btn onClick={finish}>Done</Btn>
          </div>
        </div>
        {msg && <p role="alert" className="mb-2 text-xs text-status-out">{msg}</p>}
        <p className="mb-2 text-[11px] text-ink-subtle">Keyboard: ↑↓ move · Enter confirm · Backspace reject</p>

        {!rows.length ? (
          <Empty title="All rows reviewed" action={<Btn variant="primary" onClick={finish}>Back to documents</Btn>} />
        ) : (
          <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto pr-1" role="listbox" aria-label="Extracted rows">
            {rows.map((r, i) => (
              <RowCard key={r.id} r={r} active={i === sel} i={i} biomarkers={data.biomarkers}
                onSelect={() => setSel(i)}
                onPatch={(p) => void patch(r, p)}
                onConfirm={() => void confirmOne(r)}
                onReject={() => void rejectOne(r)}
                onPicker={() => { setSel(i); setPicker(true); }}
                conflict={conflictsById.get(r.id) ?? []}
                docs={data.docs}
                busy={busy}
                onResolve={(keep) => void resolveConflict(r, keep, conflictsById.get(r.id) ?? [])}
              />
            ))}
            <Btn className="w-full" onClick={async () => {
              const r = await api.addResult({
                document_id: doc.id, profile_id: doc.profile_id, raw_test_name: "New test", raw_value: "",
                page, confidence: 1, confidence_reasons: ["manual"], status: "pending_review", flag: "unknown", comparator: "=",
              });
              setRows((xs) => [...(xs ?? []), r]);
              setSel(rows.length);
            }}>+ Add missing row</Btn>
          </div>
        )}
      </div>

      {picker && row && (
        <BiomarkerPicker biomarkers={[...data.biomarkers.values()]}
          onClose={() => setPicker(false)}
          onPick={async (b, remember) => {
            await patch(row, { biomarker_id: b.id });
            if (remember) await api.remember(row.raw_test_name, b.id);
            setPicker(false);
          }} />
      )}
    </div>
  );
}

function RowCard({ r, active, i, biomarkers, onSelect, onPatch, onConfirm, onReject, onPicker, conflict, docs, busy, onResolve }: {
  r: Result; active: boolean; i: number; biomarkers: Map<string, Biomarker>;
  onSelect: () => void; onPatch: (p: Partial<Result>) => void; onConfirm: () => void; onReject: () => void; onPicker: () => void; conflict: Result[];
  docs: Doc[]; busy: boolean; onResolve: (keep: "new" | "existing" | "both") => void;
}) {
  const bm = r.biomarker_id ? biomarkers.get(r.biomarker_id) : undefined;
  const low = r.confidence < HIGH;
  const inp = "w-full rounded border border-hairline bg-surface px-2 py-1 text-sm tabular-nums outline-none focus:border-accent";
  return (
    <div data-i={i} role="option" aria-selected={active} onClick={onSelect}
      className={`cursor-pointer rounded-card border p-3 transition ${active ? "border-accent/60 bg-accent/5 ring-1 ring-accent/30" : "border-hairline bg-surface-raised/50 hover:border-hairline"}`}>
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 font-medium">
            {bm?.display_name ?? r.raw_test_name}
            {conflict.length > 0 && <span className="rounded-full px-1.5 py-0.5 text-[10px] font-medium text-status-borderline ring-1 ring-inset ring-status-borderline/40" title="Already recorded on this date">↔ Duplicate</span>}
          </div>
          {!bm && <button className="text-xs text-status-borderline underline-offset-2 hover:underline" onClick={(e) => { e.stopPropagation(); onPicker(); }}>Map to biomarker…</button>}
        </div>
        <div className="text-right">
          <div className={`text-xs tabular-nums ${low ? "text-status-borderline" : "text-ink-subtle"}`}>{(r.confidence * 100).toFixed(0)}%</div>
          {r.confidence_reasons?.[0] && <div className="max-w-[9rem] truncate text-[10px] text-ink-subtle" title={r.confidence_reasons.join("; ")}>{r.confidence_reasons[0]}</div>}
        </div>
      </div>
      {active && (
        <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-[10px] uppercase text-ink-subtle">Value<input className={inp} defaultValue={r.raw_value} onBlur={(e) => onPatch({ raw_value: e.target.value, value_numeric: parseFloat(e.target.value) || null })} /></label>
            <label className="text-[10px] uppercase text-ink-subtle">Unit<input className={inp} defaultValue={r.raw_unit ?? ""} onBlur={(e) => onPatch({ raw_unit: e.target.value })} /></label>
            <label className="text-[10px] uppercase text-ink-subtle">Date<input type="date" className={inp} defaultValue={(r.collected_at ?? "").slice(0, 10)} onBlur={(e) => onPatch({ collected_at: e.target.value ? `${e.target.value}T08:00:00Z` : null })} /></label>
          </div>
          {conflict.length > 0 ? (
            <ConflictPanel r={r} existing={conflict} bm={bm} docs={docs} busy={busy} onResolve={onResolve} onPicker={onPicker} />
          ) : (
            <div className="flex gap-2">
              <Btn variant="primary" onClick={onConfirm}>Confirm</Btn>
              <Btn onClick={onPicker}>Biomarker</Btn>
              <Btn variant="danger" onClick={onReject}>Reject</Btn>
            </div>
          )}
        </div>
      )}
      {!active && (
        <div className="flex items-center justify-between text-sm">
          <span className="tabular-nums">{r.comparator !== "=" ? r.comparator : ""}{r.raw_value} <span className="text-ink-subtle">{r.raw_unit}</span></span>
          <StatusChip s={r.flag === "normal" ? "normal" : r.flag === "unknown" ? "unknown" : "out"} dir={r.flag === "low" || r.flag === "high" ? r.flag : null} compact />
        </div>
      )}
    </div>
  );
}

/** Side-by-side duplicate comparison (§6.10): new extracted row vs already-confirmed result(s) for the same biomarker + day. */
function ConflictPanel({ r, existing, bm, docs, busy, onResolve, onPicker }: {
  r: Result; existing: Result[]; bm?: Biomarker; docs: Doc[]; busy: boolean;
  onResolve: (keep: "new" | "existing" | "both") => void; onPicker: () => void;
}) {
  const dec = bm?.decimals ?? 1;
  const nv = r.normalized_value ?? r.value_numeric;
  const n = existing.length;
  return (
    <section aria-label="Duplicate comparison" className="rounded-lg border border-status-borderline/40 bg-status-borderline/[0.04] p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-semibold text-status-borderline"><span aria-hidden>↔ </span>Already recorded on {fmtDate(r.collected_at)}</h3>
        <span className="text-[10px] text-ink-subtle">same biomarker · same day</span>
      </div>
      <div className={`grid gap-2 ${n === 1 ? "grid-cols-2" : "grid-cols-1 sm:grid-cols-2"}`}>
        <ConflictSide title="New · this report" tone="new" res={r} dec={dec} doc={docs.find((d) => d.id === r.document_id)} />
        <div className="space-y-2">
          {existing.map((c) => (
            <ConflictSide key={c.id} title="Existing · confirmed" tone="old" res={c} dec={dec}
              doc={docs.find((d) => d.id === c.document_id)} delta={nv != null && (c.normalized_value ?? c.value_numeric) != null ? nv - (c.normalized_value ?? c.value_numeric)! : null} />
          ))}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2" role="group" aria-label="Resolve duplicate">
        <Btn variant="primary" disabled={busy} onClick={() => onResolve("new")} title={`Confirm this row and remove the existing ${n > 1 ? `${n} results` : "result"} for this day (audited)`}>Keep new</Btn>
        <Btn disabled={busy} onClick={() => onResolve("existing")} title="Reject this row; the existing result stays">Keep existing</Btn>
        <Btn disabled={busy} onClick={() => onResolve("both")} title="Confirm this row and keep the existing result too">Keep both</Btn>
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-ink-subtle">
        Keep new replaces the existing value (it is marked rejected, recorded in the audit log). Keep both stores two readings for the day — useful for genuine repeat tests.
        {" "}<button className="underline-offset-2 hover:underline" onClick={onPicker}>Wrong biomarker?</button>
      </p>
    </section>
  );
}

function ConflictSide({ title, tone, res, dec, doc, delta }: { title: string; tone: "new" | "old"; res: Result; dec: number; doc?: Doc; delta?: number | null }) {
  const v = res.normalized_value ?? res.value_numeric;
  const st = resultStatus(res);
  const range = res.ref_low != null || res.ref_high != null ? `${res.ref_low != null ? fmt(res.ref_low, dec) : "<"}–${res.ref_high != null ? fmt(res.ref_high, dec) : "…"}` : res.raw_ref_text ?? "—";
  const same = delta != null && Math.abs(delta) < 0.5 * 10 ** -dec;
  return (
    <div className={`rounded-md border p-2.5 ${tone === "new" ? "border-accent/40 bg-accent/5" : "border-hairline bg-surface/60"}`}>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-ink-subtle">{title}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tabular-nums tracking-tight">{res.comparator !== "=" ? res.comparator : ""}{v != null ? fmt(v, dec) : res.value_qualitative ?? res.raw_value}</span>
        <span className="text-xs text-ink-subtle">{res.canonical_unit ?? res.raw_unit}</span>
      </div>
      {res.raw_unit && res.canonical_unit && res.raw_unit !== res.canonical_unit && (
        <div className="text-[10px] tabular-nums text-ink-subtle">as printed: {res.raw_value} {res.raw_unit}</div>
      )}
      <dl className="mt-2 space-y-0.5 text-[11px] text-ink-muted">
        <div className="flex justify-between gap-2"><dt className="text-ink-subtle">Status</dt><dd><StatusChip s={st} dir={direction(res)} /></dd></div>
        <div className="flex justify-between gap-2"><dt className="text-ink-subtle">Range</dt><dd className="tabular-nums">{range}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-ink-subtle">Collected</dt><dd className="tabular-nums">{fmtDate(res.collected_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</dd></div>
        <div className="flex justify-between gap-2"><dt className="text-ink-subtle">Source</dt><dd className="max-w-[9rem] truncate" title={doc?.original_filename}>{doc?.lab_name ?? doc?.original_filename ?? "—"}</dd></div>
      </dl>
      {delta != null && (
        <div className="mt-2 border-t border-hairline pt-1.5 text-[11px] tabular-nums text-ink-muted">
          {same ? <><span aria-hidden>= </span>Same value as new</> : <><span aria-hidden>{delta > 0 ? "▲" : "▼"} </span>New is {fmt(Math.abs(delta), dec)} {delta > 0 ? "higher" : "lower"}{v != null && v - delta !== 0 ? ` (${fmt(Math.abs(delta / (v - delta)) * 100, 0)}%)` : ""}</>}
        </div>
      )}
    </div>
  );
}

function BiomarkerPicker({ biomarkers, onClose, onPick }: { biomarkers: Biomarker[]; onClose: () => void; onPick: (b: Biomarker, remember: boolean) => void }) {
  const [q, setQ] = useState("");
  const [remember, setRemember] = useState(true);
  const list = biomarkers.filter((b) => !q || b.display_name.toLowerCase().includes(q.toLowerCase()) || b.category.toLowerCase().includes(q.toLowerCase())).slice(0, 40);
  return (
    <div className="fixed inset-0 z-50 grid place-items-end bg-black/50 p-4 sm:place-items-center" role="dialog" aria-label="Pick biomarker" onClick={onClose}>
      <Card className="max-h-[80vh] w-full max-w-md overflow-hidden" as="div">
        <div className="border-b border-hairline p-4" onClick={(e) => e.stopPropagation()}>
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Map to biomarker</h2><Btn onClick={onClose}>✕</Btn></div>
          <input autoFocus className="w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="mt-2 flex items-center gap-2 text-xs text-ink-muted"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember this mapping for future reports</label>
        </div>
        <ul className="max-h-80 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
          {list.map((b) => (
            <li key={b.id}><button className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-surface-overlay" onClick={() => onPick(b, remember)}>
              <span>{b.display_name}</span><span className="text-xs text-ink-subtle">{b.category}</span>
            </button></li>
          ))}
          {!list.length && <li className="px-4 py-6 text-center text-sm text-ink-subtle">No matches</li>}
        </ul>
      </Card>
    </div>
  );
}

function DocMetaEditor({ doc, onSaved }: { doc: Doc; onSaved: (d: Doc) => void }) {
  const [open, setOpen] = useState(false);
  const [lab, setLab] = useState(doc.lab_name ?? "");
  const [reportDate, setReportDate] = useState((doc.report_date ?? "").slice(0, 10));
  const [collected, setCollected] = useState((doc.collected_at ?? "").slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    setLab(doc.lab_name ?? "");
    setReportDate((doc.report_date ?? "").slice(0, 10));
    setCollected((doc.collected_at ?? "").slice(0, 10));
    setErr(null);
  }, [open, doc]);
  if (!open) {
    return <Btn onClick={() => setOpen(true)} title="Edit lab name and dates">Edit meta</Btn>;
  }
  const inp = "w-full rounded border border-hairline bg-surface px-2 py-1 text-sm outline-none focus:border-accent";
  return (
    <div className="w-full basis-full rounded-lg border border-hairline bg-surface p-3 text-left sm:basis-auto sm:min-w-[18rem]" onClick={(e) => e.stopPropagation()}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-medium text-ink">Document details</span>
        <Btn onClick={() => setOpen(false)}>✕</Btn>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        <label className="text-[10px] uppercase text-ink-subtle">Lab name<input className={inp} value={lab} onChange={(e) => setLab(e.target.value)} /></label>
        <label className="text-[10px] uppercase text-ink-subtle">Report date<input type="date" className={inp} value={reportDate} onChange={(e) => setReportDate(e.target.value)} /></label>
        <label className="text-[10px] uppercase text-ink-subtle">Collected<input type="date" className={inp} value={collected} onChange={(e) => setCollected(e.target.value)} /></label>
      </div>
      {err && <p role="alert" className="mt-2 text-xs text-status-out">{err}</p>}
      <div className="mt-2 flex gap-2">
        <Btn variant="primary" disabled={busy} onClick={() => void (async () => {
          setBusy(true); setErr(null);
          try {
            const updated = await api.updateDocument(doc.id, {
              lab_name: lab.trim() || null,
              report_date: reportDate || null,
              collected_at: collected ? `${collected}T08:00:00Z` : null,
            });
            onSaved({ ...doc, ...updated });
            setOpen(false);
          } catch (e) { setErr((e as Error).message); }
          finally { setBusy(false); }
        })()}>Save</Btn>
        <Btn disabled={busy} onClick={() => setOpen(false)}>Cancel</Btn>
      </div>
    </div>
  );
}

function PlaceholderPage({ page, highlight, row }: { page: number; highlight?: number[] | null; row?: Result }) {
  return (
    <div className="relative aspect-[3/4] w-full bg-[#f4f1ea] text-[#1a1a1a] shadow-soft">
      <div className="px-8 pt-10 font-serif text-sm opacity-60">Page {page} · source preview unavailable</div>
      <div className="mt-6 space-y-3 px-8">
        {Array.from({ length: 12 }, (_, i) => (
          <div key={i} className="flex justify-between gap-4 border-b border-black/10 pb-1 text-xs">
            <span className="w-1/2 truncate opacity-50">Test name {i + 1}</span>
            <span className="tabular-nums opacity-40">——</span>
            <span className="opacity-30">— — —</span>
          </div>
        ))}
      </div>
      {highlight && highlight.length >= 4 && (
        <div className="absolute border-2 border-teal-600 bg-teal-500/20"
          style={{ left: `${highlight[0]! * 100}%`, top: `${highlight[1]! * 100}%`, width: `${(highlight[2]! - highlight[0]!) * 100}%`, height: `${(highlight[3]! - highlight[1]!) * 100}%` }}>
          {row && <div className="absolute -top-5 left-0 whitespace-nowrap bg-teal-700 px-1.5 text-[10px] text-white">{row.raw_test_name}: {row.raw_value}</div>}
        </div>
      )}
    </div>
  );
}
