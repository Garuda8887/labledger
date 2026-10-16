import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Btn } from "./ui";

/** File picker (multi PDF/image) + camera capture on mobile. */
export function Upload({ big }: { big?: boolean }) {
  const { profile, reloadData } = useApp();
  const nav = useNavigate();
  const file = useRef<HTMLInputElement>(null);
  const cam = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function go(fl: FileList | null) {
    if (!fl?.length || !profile) return;
    setBusy(true); setErr(null);
    try {
      const docs = await api.upload(profile.id, [...fl]);
      reloadData();
      nav(docs[0] ? `/review/${docs[0].id}` : "/documents");
    } catch (e) { setErr((e as Error).message || "Upload failed"); }
    finally { setBusy(false); if (file.current) file.current.value = ""; if (cam.current) cam.current.value = ""; }
  }
  return (
    <div className={`flex flex-wrap items-center gap-2 ${big ? "justify-center" : ""}`}>
      <input ref={file} type="file" multiple accept="application/pdf,image/*" className="sr-only" onChange={(e) => go(e.target.files)} aria-label="Upload reports" />
      <input ref={cam} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => go(e.target.files)} aria-label="Capture with camera" />
      <Btn variant="primary" disabled={busy} onClick={() => file.current?.click()} className={big ? "px-5 py-2.5 text-base" : ""}>{busy ? "Uploading…" : "Upload reports"}</Btn>
      <Btn disabled={busy} onClick={() => cam.current?.click()} className={big ? "px-5 py-2.5 text-base sm:hidden" : "sm:hidden"}>Camera</Btn>
      {err && <p role="alert" className="w-full text-center text-xs text-status-out">{err}</p>}
    </div>
  );
}
