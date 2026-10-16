/**
 * API client for /api/v1 (proxied by Vite to 127.0.0.1:8000).
 * Every call degrades gracefully: missing endpoints (404/405/501/network) resolve to empty data
 * so pages render empty states. When demo mode is on, a fabricated in-memory dataset is used instead.
 * Cookie credentials are always sent so APP_PASSPHRASE session lock works across the Vite proxy.
 */
import { buildMock, mockBiomarkers } from "./mock";
import type { Biomarker, Doc, Profile, Result } from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message); }
}
export const isDemo = () => localStorage.getItem("labledger.demo") === "1";
export const setDemo = (on: boolean) => { localStorage.setItem("labledger.demo", on ? "1" : "0"); location.reload(); };

let mock: ReturnType<typeof buildMock> | null = null;
const M = () => (mock ??= buildMock());

async function req<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body = init?.body;
  if (init?.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.json); }
  const r = await fetch(BASE + path, {
    ...init,
    body,
    credentials: "include",
    headers: { ...headers, ...(init?.headers as object) },
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    let code: string | undefined;
    try {
      const j = await r.json();
      const detail = j.detail;
      if (typeof detail === "string") msg = detail;
      else if (detail && typeof detail === "object") {
        msg = typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail);
        code = detail.code ?? j.code;
      } else {
        msg = JSON.stringify(j.detail ?? j);
        code = j.code;
      }
    } catch { /* ignore */ }
    throw new ApiError(r.status, msg, code);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}
/** Reads tolerate unimplemented endpoints. */
async function soft<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch (e) {
    if (e instanceof ApiError && e.code === "app_locked") throw e;
    if (e instanceof ApiError && ![404, 405, 501, 502, 503, 504].includes(e.status)) throw e;
    return fallback;
  }
}
const list = <T,>(x: T[] | { items: T[] }): T[] => (Array.isArray(x) ? x : x?.items ?? []);
const qs = (o: Record<string, string | undefined>) => {
  const p = new URLSearchParams(); Object.entries(o).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString(); return s ? `?${s}` : "";
};

export type AuthStatus = { locked: boolean; unlocked: boolean };

export const api = {
  health: () => req<{ status: string; version: string; db: string }>("/health"),

  async authStatus(): Promise<AuthStatus> {
    if (isDemo()) return { locked: false, unlocked: true };
    return soft(req<AuthStatus>("/auth/status"), { locked: false, unlocked: true });
  },
  async unlock(passphrase: string): Promise<void> {
    await req("/auth/unlock", { method: "POST", json: { passphrase } });
  },
  async lock(): Promise<void> {
    if (isDemo()) return;
    await soft(req("/auth/lock", { method: "POST" }), undefined as unknown as void);
  },

  async profiles(): Promise<Profile[]> {
    if (isDemo()) return M().profiles;
    return list(await soft(req<Profile[]>("/profiles"), []));
  },
  async createProfile(p: Pick<Profile, "display_name" | "dob" | "sex">): Promise<Profile> {
    if (isDemo()) { const np = { ...p, id: crypto.randomUUID(), preferred_unit_system: "conventional", created_at: new Date().toISOString() }; M().profiles.push(np); return np; }
    return req("/profiles", { method: "POST", json: p });
  },
  async updateProfile(id: string, p: Partial<Profile>): Promise<Profile> {
    if (isDemo()) { const x = M().profiles.find((q) => q.id === id)!; Object.assign(x, p); return x; }
    return req(`/profiles/${id}`, { method: "PATCH", json: p });
  },

  async documents(profile_id: string): Promise<Doc[]> {
    if (isDemo()) return M().docs.filter((d) => d.profile_id === profile_id);
    return list(await soft(req<Doc[]>(`/profiles/${profile_id}/documents`), []));
  },
  async document(id: string): Promise<Doc | null> {
    if (isDemo()) return M().docs.find((d) => d.id === id) ?? null;
    return soft(req<Doc>(`/documents/${id}`), null);
  },
  async updateDocument(id: string, p: Partial<Doc>): Promise<Doc> {
    if (isDemo()) { const d = M().docs.find((x) => x.id === id)!; Object.assign(d, p); return d; }
    return req(`/documents/${id}/metadata`, { method: "PATCH", json: p });
  },
  pageImageUrl: (docId: string, page: number) => (isDemo() ? null : `${BASE}/documents/${docId}/pages/${page}`),
  async upload(profile_id: string, files: File[]): Promise<Doc[]> {
    if (isDemo()) throw new ApiError(400, "Uploads are disabled in demo mode");
    const fd = new FormData(); files.forEach((f) => fd.append("files", f));
    const r = await req<{ documents: Doc[] } | Doc[]>(`/profiles/${profile_id}/documents`, { method: "POST", body: fd });
    return Array.isArray(r) ? r : r.documents ?? [];
  },

  async results(f: { profile_id: string; biomarker_id?: string; status?: string; document_id?: string }): Promise<Result[]> {
    if (isDemo()) return M().results.filter((r) => r.profile_id === f.profile_id && (!f.biomarker_id || r.biomarker_id === f.biomarker_id) && (!f.status || r.status === f.status) && (!f.document_id || r.document_id === f.document_id));
    const out: Result[] = [];
    for (let offset = 0; offset < 20000; offset += 1000) {
      const page = list(await soft(req<Result[]>(`/results${qs({ ...f, limit: "1000", offset: String(offset) })}`), []));
      out.push(...page);
      if (page.length < 1000) break;
    }
    return out;
  },
  async updateResult(id: string, p: Partial<Result>): Promise<Result> {
    if (isDemo()) { const r = M().results.find((x) => x.id === id)!; Object.assign(r, p); return r; }
    return req(`/results/${id}`, { method: "PATCH", json: p });
  },
  async confirm(id: string): Promise<Result> { return isDemo() ? api.updateResult(id, { status: "confirmed" }) : req(`/results/${id}/confirm`, { method: "POST" }); },
  async reject(id: string): Promise<Result> { return isDemo() ? api.updateResult(id, { status: "rejected" }) : req(`/results/${id}/reject`, { method: "POST" }); },
  async bulkConfirm(ids: string[]): Promise<void> {
    if (isDemo()) { ids.forEach((id) => { const r = M().results.find((x) => x.id === id); if (r) r.status = "confirmed"; }); return; }
    try { await req("/results/bulk-confirm", { method: "POST", json: { result_ids: ids } }); }
    catch (e) { if (e instanceof ApiError && e.status === 404) await Promise.all(ids.map(api.confirm)); else throw e; }
  },
  async addResult(r: Partial<Result> & { document_id: string; profile_id: string }): Promise<Result> {
    if (isDemo()) { const full = { ...r, id: crypto.randomUUID(), status: "pending_review", confidence: 1, confidence_reasons: ["added manually"] } as Result; M().results.push(full); return full; }
    return req("/results", { method: "POST", json: r });
  },
  async remember(raw_name: string, biomarker_id: string): Promise<void> {
    if (isDemo()) return;
    await req("/learned-aliases", { method: "POST", json: { raw_name, biomarker_id } });
  },

  async biomarkers(q?: string): Promise<Biomarker[]> {
    if (isDemo()) return mockBiomarkers.filter((b) => !q || b.display_name.toLowerCase().includes(q.toLowerCase()));
    return list(await soft(req<(Biomarker & { canonical_key?: string })[]>(`/biomarkers${qs({ q, limit: "500" })}`), [])).map((b) => ({
      ...b,
      key: b.key ?? b.canonical_key,
      alt_unit: b.alt_unit ?? null,
      alt_factor: b.alt_factor ?? null,
    }));
  },

  /** A's export is a zip (JSON + originals); no format query param. */
  exportUrl: (profile_id: string) => `${BASE}/profiles/${profile_id}/export`,
};
